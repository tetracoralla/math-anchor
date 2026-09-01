from __future__ import annotations

import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import time
from typing import Any

from .certificate_checker import (
    CertificateValidationError,
    MAX_AST_NODES,
    MAX_POLYNOMIAL_DEGREE,
    verify_polynomial_identity_certificate,
)
from .errors import CalculatorError


LEAN_CHECKER_SYSTEM = "Lean"
LEAN_BRIDGE_VERSION = "1.0.0"
LEAN_VERSION = "4.33.1"
LEAN_TOOLCHAIN = f"leanprover/lean4:v{LEAN_VERSION}"
MATHLIB_REVISION = "0df444a360eaa60ab8c11dca51a86af692955474"
MAX_KERNEL_OUTPUT_BYTES = 65_536
_LEAN_VERSION = re.compile(r"^Lean \(version ([^)]+)\)")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_AXIOM_REPORT = re.compile(r"depends on axioms:\s*\[[^\r\n]*\]")


class _LeanExpressionTranslator(ast.NodeVisitor):
    """Translate the certificate grammar into fully parenthesized Lean terms.

    User-provided variable names are replaced by generated identifiers. Only
    the already bounded polynomial grammar is accepted; no source text is
    copied into the Lean artifact.
    """

    def __init__(self, variables: list[str]) -> None:
        self.variable_map = {name: f"v{index}" for index, name in enumerate(variables)}
        self.nodes = 0

    def visit(self, node: ast.AST) -> str:  # type: ignore[override]
        self.nodes += 1
        if self.nodes > MAX_AST_NODES:
            raise CertificateValidationError("certificate expression exceeds the Lean bridge AST limit")
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> str:
        raise CertificateValidationError(
            f"unsupported Lean bridge syntax: {type(node).__name__}"
        )

    def visit_Expression(self, node: ast.Expression) -> str:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> str:
        if not isinstance(node.value, int) or isinstance(node.value, bool):
            raise CertificateValidationError("Lean bridge accepts only integer literals")
        return f"({node.value} : ℚ)"

    def visit_Name(self, node: ast.Name) -> str:
        try:
            return self.variable_map[node.id]
        except KeyError as error:
            raise CertificateValidationError(
                f"unknown Lean bridge variable: {node.id}"
            ) from error

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return f"(+{value})"
        if isinstance(node.op, ast.USub):
            return f"(-{value})"
        return self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> str:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return f"({left} + {right})"
        if isinstance(node.op, ast.Sub):
            return f"({left} - {right})"
        if isinstance(node.op, ast.Mult):
            return f"({left} * {right})"
        if isinstance(node.op, ast.Div):
            return f"({left} / {right})"
        if isinstance(node.op, ast.Pow):
            if (
                not isinstance(node.right, ast.Constant)
                or not isinstance(node.right.value, int)
                or isinstance(node.right.value, bool)
                or not 0 <= node.right.value <= MAX_POLYNOMIAL_DEGREE
            ):
                raise CertificateValidationError(
                    "Lean bridge exponents must be bounded nonnegative integers"
                )
            return f"({left} ^ {node.right.value})"
        return self.generic_visit(node)

    def translate(self, source: str) -> str:
        try:
            parsed = ast.parse(source, mode="eval")
        except SyntaxError as error:
            raise CertificateValidationError(
                "certificate expression has invalid Lean bridge syntax"
            ) from error
        return self.visit(parsed)


def _digest(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def build_lean_artifact(certificate: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    checked = verify_polynomial_identity_certificate(certificate)
    if checked["identity"] is not True:
        raise CertificateValidationError(
            "Lean kernel checking requires a certificate whose identity classification is true"
        )
    statement = certificate["statement"]
    variables = statement["variables"]
    left_translator = _LeanExpressionTranslator(variables)
    right_translator = _LeanExpressionTranslator(variables)
    left = left_translator.translate(statement["left"])
    right = right_translator.translate(statement["right"])
    theorem_name = f"certificate_{certificate['certificateDigest'].split(':', 1)[1][:16]}"
    binders = " ".join(left_translator.variable_map[name] for name in variables)
    source = (
        "import Mathlib.Tactic.Ring\n\n"
        "namespace MathAnchorCertificate\n\n"
        f"-- Certificate: {certificate['certificateDigest']}\n"
        "set_option autoImplicit false\n\n"
        f"theorem {theorem_name} ({binders} : ℚ) :\n"
        f"    {left} = {right} := by\n"
        "  ring\n\n"
        f"#print axioms {theorem_name}\n\n"
        "end MathAnchorCertificate\n"
    )
    metadata = {
        "theorem": theorem_name,
        "variableMap": dict(left_translator.variable_map),
        "statementDigest": certificate["statementDigest"],
        "certificateDigest": certificate["certificateDigest"],
        "stdlibChecker": checked["checker"],
    }
    return source, metadata


def _bounded_text(value: bytes) -> str:
    truncated = len(value) > MAX_KERNEL_OUTPUT_BYTES
    value = value[:MAX_KERNEL_OUTPUT_BYTES]
    text = value.decode("utf-8", errors="replace")
    return f"{text}...<truncated>" if truncated else text


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _run(
    command: list[str], *, cwd: Path, timeout: float
) -> subprocess.CompletedProcess[str]:
    if timeout <= 0:
        raise CalculatorError("E_TIMEOUT", "Lean kernel checking exceeded its deadline")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise CalculatorError("E_UNAVAILABLE", f"Lean could not be started: {error}") from error
    selector = selectors.DefaultSelector()
    streams = {"stdout": process.stdout, "stderr": process.stderr}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    for name, stream in streams.items():
        assert stream is not None
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            for key, _ in selector.select(timeout=min(remaining, 0.1)):
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 65_536)
                if not chunk:
                    selector.unregister(stream)
                    continue
                buffer = buffers[key.data]
                capacity = MAX_KERNEL_OUTPUT_BYTES + 1 - len(buffer)
                if capacity > 0:
                    buffer.extend(chunk[:capacity])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as error:
        _kill_process_group(process)
        raise CalculatorError("E_TIMEOUT", "Lean kernel checking exceeded its deadline") from error
    finally:
        selector.close()
        for stream in streams.values():
            if stream is not None:
                stream.close()
    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout=_bounded_text(bytes(buffers["stdout"])),
        stderr=_bounded_text(bytes(buffers["stderr"])),
    )


def _validate_project_lock(project_root: Path) -> dict[str, str]:
    try:
        toolchain = (project_root / "lean-toolchain").read_text(encoding="utf-8").strip()
        lakefile = (project_root / "lakefile.toml").read_text(encoding="utf-8")
        manifest_bytes = (project_root / "lake-manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise CalculatorError(
            "E_INPUT",
            "Lean bridge project must contain a readable pinned toolchain and manifest",
        ) from error
    packages = manifest.get("packages") if isinstance(manifest, dict) else None
    mathlib = next(
        (
            package
            for package in packages or []
            if isinstance(package, dict) and package.get("name") == "mathlib"
        ),
        None,
    )
    revisions_are_exact = bool(packages) and all(
        isinstance(package, dict)
        and isinstance(package.get("rev"), str)
        and _REVISION.fullmatch(package["rev"])
        for package in packages
    )
    lakefile_is_pinned = f'rev = "{MATHLIB_REVISION}"' in lakefile
    if (
        toolchain != LEAN_TOOLCHAIN
        or mathlib is None
        or mathlib.get("rev") != MATHLIB_REVISION
        or not revisions_are_exact
        or not lakefile_is_pinned
    ):
        raise CalculatorError(
            "E_INPUT",
            "Lean bridge project does not match the pinned Lean and Mathlib revisions",
        )
    return {"manifestDigest": _digest(manifest_bytes)}


def _validate_kernel_output(value: str) -> None:
    if "...<truncated>" in value:
        raise CalculatorError("E_KERNEL", "Lean kernel output exceeded the supported limit")
    if "sorryAx" in value:
        raise CalculatorError("E_KERNEL", "Lean theorem depends on sorryAx")
    reports = _AXIOM_REPORT.findall(value)
    if len(reports) != 1:
        raise CalculatorError("E_KERNEL", "Lean did not report the generated theorem's axioms")


def verify_polynomial_identity_with_lean(
    certificate: dict[str, Any],
    *,
    lake: Path,
    project_root: Path,
    artifact_output: Path | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
        raise CalculatorError("E_INPUT", "Lean timeout must be an integer from 1 through 600 seconds")
    source, metadata = build_lean_artifact(certificate)
    project_root = project_root.resolve()
    lake = lake.resolve()
    if not lake.is_file():
        raise CalculatorError("E_UNAVAILABLE", f"Lake executable is unavailable: {lake}")
    if not (project_root / "lakefile.toml").is_file():
        raise CalculatorError("E_INPUT", f"Lean bridge project is unavailable: {project_root}")
    lock_metadata = _validate_project_lock(project_root)
    deadline = time.monotonic() + timeout

    version_result = _run(
        [str(lake), "env", "lean", "--version"],
        cwd=project_root,
        timeout=deadline - time.monotonic(),
    )
    version_output = (version_result.stdout or version_result.stderr).strip().splitlines()
    match = _LEAN_VERSION.match(version_output[0]) if version_output else None
    if version_result.returncode != 0 or match is None:
        raise CalculatorError("E_UNAVAILABLE", "Lean version could not be established")
    lean_version = match.group(1)
    if lean_version.split(",", 1)[0] != LEAN_VERSION:
        raise CalculatorError(
            "E_UNAVAILABLE",
            f"Lean version mismatch: expected {LEAN_VERSION}, found {lean_version}",
        )

    source_bytes = source.encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="math-anchor-lean-") as temporary:
        temporary_path = Path(temporary) / "Certificate.lean"
        temporary_path.write_bytes(source_bytes)
        completed = _run(
            [str(lake), "env", "lean", str(temporary_path)],
            cwd=project_root,
            timeout=deadline - time.monotonic(),
        )
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        if len(diagnostic) > 2_000:
            diagnostic = f"{diagnostic[:2_000]}..."
        raise CalculatorError(
            "E_KERNEL",
            f"Lean rejected the generated theorem: {diagnostic or 'unknown compiler error'}",
        )
    kernel_output = f"{completed.stdout}\n{completed.stderr}"
    _validate_kernel_output(kernel_output)

    if artifact_output is not None:
        artifact_output = artifact_output.resolve()
        artifact_output.parent.mkdir(parents=True, exist_ok=True)
        artifact_output.write_bytes(source_bytes)

    artifact_digest = _digest(source_bytes)
    return {
        "status": "ok",
        "kind": "kernel_certificate_check",
        "valid": True,
        "identity": True,
        "assurance": "kernel_checked",
        "scope": "polynomial_identity_over_rationals",
        "bridgeVersion": LEAN_BRIDGE_VERSION,
        **metadata,
        "artifactDigest": artifact_digest,
        "checkedBy": {
            "system": LEAN_CHECKER_SYSTEM,
            "version": f"{lean_version}+mathlib@{MATHLIB_REVISION}",
            "artifactDigest": artifact_digest,
            "lakeDigest": _digest(lake.read_bytes()),
            **lock_metadata,
        },
    }
