from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import tempfile
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
_LEAN_VERSION = re.compile(r"^Lean \(version ([^)]+)\)")


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
        return str(node.value)

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
    translator = _LeanExpressionTranslator(variables)
    left = translator.translate(statement["left"])
    right = translator.translate(statement["right"])
    theorem_name = f"certificate_{certificate['certificateDigest'].split(':', 1)[1][:16]}"
    binders = " ".join(translator.variable_map[name] for name in variables)
    source = (
        "import Mathlib.Tactic\n\n"
        "namespace MathAnchorCertificate\n\n"
        f"-- Certificate: {certificate['certificateDigest']}\n"
        f"theorem {theorem_name} ({binders} : ℚ) :\n"
        f"    {left} = {right} := by\n"
        "  ring\n\n"
        "end MathAnchorCertificate\n"
    )
    metadata = {
        "theorem": theorem_name,
        "variableMap": dict(translator.variable_map),
        "statementDigest": certificate["statementDigest"],
        "certificateDigest": certificate["certificateDigest"],
        "stdlibChecker": checked["checker"],
    }
    return source, metadata


def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise CalculatorError("E_TIMEOUT", "Lean kernel checking exceeded its deadline") from error
    except OSError as error:
        raise CalculatorError("E_UNAVAILABLE", f"Lean could not be started: {error}") from error


def verify_polynomial_identity_with_lean(
    certificate: dict[str, Any],
    *,
    lake: Path,
    project_root: Path,
    artifact_output: Path | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    source, metadata = build_lean_artifact(certificate)
    project_root = project_root.resolve()
    lake = lake.resolve()
    if not lake.is_file():
        raise CalculatorError("E_UNAVAILABLE", f"Lake executable is unavailable: {lake}")
    if not (project_root / "lakefile.toml").is_file():
        raise CalculatorError("E_INPUT", f"Lean bridge project is unavailable: {project_root}")

    version_result = _run([str(lake), "env", "lean", "--version"], cwd=project_root, timeout=30)
    version_output = (version_result.stdout or version_result.stderr).strip().splitlines()
    match = _LEAN_VERSION.match(version_output[0]) if version_output else None
    if version_result.returncode != 0 or match is None:
        raise CalculatorError("E_UNAVAILABLE", "Lean version could not be established")
    lean_version = match.group(1)

    source_bytes = source.encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="math-anchor-lean-") as temporary:
        temporary_path = Path(temporary) / "Certificate.lean"
        temporary_path.write_bytes(source_bytes)
        completed = _run(
            [str(lake), "env", "lean", str(temporary_path)],
            cwd=project_root,
            timeout=timeout,
        )
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        if len(diagnostic) > 2_000:
            diagnostic = f"{diagnostic[:2_000]}..."
        raise CalculatorError(
            "E_KERNEL",
            f"Lean rejected the generated theorem: {diagnostic or 'unknown compiler error'}",
        )

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
            "version": lean_version,
            "artifactDigest": artifact_digest,
        },
    }
