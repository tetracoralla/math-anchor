#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

from math_anchor.certificate_checker import (
    CertificateValidationError,
    MAX_AST_NODES,
    MAX_POLYNOMIAL_DEGREE,
    verify_polynomial_identity_certificate,
)


ROOT = Path(__file__).resolve().parent.parent
BUILD_ROOT = Path(
    os.environ.get(
        "MATH_ANCHOR_LEAN_STATE_DIR",
        f"/private/tmp/math-anchor-lean-reference-{os.getuid()}",
    )
)
ELAN_HOME = BUILD_ROOT / "elan-home"
ELAN = ELAN_HOME / "bin" / "elan"
PROJECT = BUILD_ROOT / "project"
TOOLCHAIN = "leanprover/lean4:v4.33.1"
MATHLIB_REVISION = "0df444a360eaa60ab8c11dca51a86af692955474"
MAX_INPUT_BYTES = 1_048_576
MAX_KERNEL_OUTPUT_BYTES = 65_536
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_AXIOM_REPORT = re.compile(r"depends on axioms:\s*\[[^\r\n]*\]")


class LeanReferenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _Translated:
    source: str
    constant: Fraction | None


class _LeanExpressionTranslator:
    def __init__(self, variables: list[str]) -> None:
        self._variables = {name: f"v{index}" for index, name in enumerate(variables)}
        self._nodes = 0

    def translate(self, source: str) -> str:
        try:
            parsed = ast.parse(source, mode="eval")
        except SyntaxError as error:
            raise LeanReferenceError("E_TRANSLATION", "certificate expression has invalid syntax") from error
        return self._visit(parsed.body).source

    def _visit(self, node: ast.AST) -> _Translated:
        self._nodes += 1
        if self._nodes > MAX_AST_NODES:
            raise LeanReferenceError("E_LIMIT", "certificate expression exceeds the AST limit")
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, int) or isinstance(node.value, bool):
                raise LeanReferenceError("E_TRANSLATION", "only integer literals can be translated")
            value = Fraction(node.value)
            return _Translated(f"({node.value} : ℚ)", value)
        if isinstance(node, ast.Name):
            translated = self._variables.get(node.id)
            if translated is None:
                raise LeanReferenceError("E_TRANSLATION", f"unknown certificate variable: {node.id}")
            return _Translated(translated, None)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = self._visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return _Translated(f"(+{operand.source})", operand.constant)
            value = -operand.constant if operand.constant is not None else None
            return _Translated(f"(-{operand.source})", value)
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                if (
                    not isinstance(node.right, ast.Constant)
                    or not isinstance(node.right.value, int)
                    or isinstance(node.right.value, bool)
                    or not 0 <= node.right.value <= MAX_POLYNOMIAL_DEGREE
                ):
                    raise LeanReferenceError(
                        "E_TRANSLATION",
                        "polynomial exponents must be bounded nonnegative integers",
                    )
                base = self._visit(node.left)
                value = base.constant**node.right.value if base.constant is not None else None
                return _Translated(f"({base.source} ^ {node.right.value})", value)

            left = self._visit(node.left)
            right = self._visit(node.right)
            if isinstance(node.op, ast.Add):
                value = left.constant + right.constant if left.constant is not None and right.constant is not None else None
                return _Translated(f"({left.source} + {right.source})", value)
            if isinstance(node.op, ast.Sub):
                value = left.constant - right.constant if left.constant is not None and right.constant is not None else None
                return _Translated(f"({left.source} - {right.source})", value)
            if isinstance(node.op, ast.Mult):
                value = left.constant * right.constant if left.constant is not None and right.constant is not None else None
                return _Translated(f"({left.source} * {right.source})", value)
            if isinstance(node.op, ast.Div):
                if right.constant is None or right.constant == 0:
                    raise LeanReferenceError(
                        "E_TRANSLATION",
                        "polynomial division requires a nonzero rational constant",
                    )
                value = left.constant / right.constant if left.constant is not None else None
                return _Translated(f"({left.source} / {right.source})", value)
        raise LeanReferenceError(
            "E_TRANSLATION",
            f"unsupported certificate syntax: {type(node).__name__}",
        )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _load_json(source: str) -> dict[str, Any]:
    if source == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        try:
            with Path(source).open("rb") as handle:
                raw = handle.read(MAX_INPUT_BYTES + 1)
        except OSError as error:
            raise LeanReferenceError("E_INPUT", f"certificate file could not be read: {error}") from error
    if len(raw) > MAX_INPUT_BYTES:
        raise LeanReferenceError("E_LIMIT", f"certificate input may contain at most {MAX_INPUT_BYTES} bytes")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LeanReferenceError("E_INPUT", f"invalid certificate JSON: {error}") from error
    if not isinstance(value, dict):
        raise LeanReferenceError("E_INPUT", "certificate JSON must be an object")
    nested = value.get("certificate", value)
    if not isinstance(nested, dict):
        raise LeanReferenceError("E_INPUT", "result certificate must be an object")
    return nested


def _fixture_certificate(fixture_id: str) -> dict[str, Any]:
    # The producer is intentionally imported only for the tracked end-to-end
    # fixture. Ordinary certificate consumption remains independent of SymPy
    # and the producing operation registry.
    from math_anchor.runtime import execute_direct

    fixture_path = ROOT / "evals" / "research" / f"{fixture_id}.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LeanReferenceError("E_INPUT", f"research fixture could not be read: {error}") from error
    if not isinstance(fixture, dict) or fixture.get("operation") != "certificate.polynomial_identity":
        raise LeanReferenceError("E_INPUT", "research fixture operation is invalid")
    arguments = fixture.get("arguments")
    if not isinstance(arguments, dict):
        raise LeanReferenceError("E_INPUT", "research fixture arguments are invalid")
    result = execute_direct("certificate.polynomial_identity", arguments)
    certificate = result.get("certificate")
    if not isinstance(certificate, dict):
        raise LeanReferenceError("E_CERTIFICATE", "fixture did not produce a certificate")
    return certificate


def build_lean_source(certificate: dict[str, Any]) -> bytes:
    try:
        check = verify_polynomial_identity_certificate(certificate)
    except CertificateValidationError as error:
        raise LeanReferenceError("E_CERTIFICATE", str(error)) from error
    if check["identity"] is not True:
        raise LeanReferenceError("E_CERTIFICATE", "a false identity cannot receive a kernel check")

    statement = certificate["statement"]
    variables = statement["variables"]
    translator = _LeanExpressionTranslator(variables)
    left = translator.translate(statement["left"])
    translator = _LeanExpressionTranslator(variables)
    right = translator.translate(statement["right"])
    binders = " ".join(f"v{index}" for index in range(len(variables)))
    certificate_digest = certificate["certificateDigest"]
    source = f"""import Mathlib.Tactic.Ring

-- Bound certificate: {certificate_digest}
set_option autoImplicit false

theorem mathAnchorCertificate ({binders} : ℚ) :
    {left} = {right} := by
  ring

#print axioms mathAnchorCertificate
"""
    return source.encode("utf-8")


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


def _run_bounded(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    if timeout_seconds <= 0:
        raise LeanReferenceError("E_TIMEOUT", "Lean kernel check exceeded its deadline")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise LeanReferenceError("E_TOOLCHAIN", f"Lean could not be started: {error}") from error
    selector = selectors.DefaultSelector()
    streams = {"stdout": process.stdout, "stderr": process.stderr}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    for name, stream in streams.items():
        assert stream is not None
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    deadline = time.monotonic() + timeout_seconds
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
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
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as error:
        _kill_process_group(process)
        raise LeanReferenceError("E_TIMEOUT", "Lean kernel check exceeded its deadline") from error
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


def _validate_project_lock() -> dict[str, str]:
    try:
        toolchain = (PROJECT / "lean-toolchain").read_text(encoding="utf-8").strip()
        lakefile = (PROJECT / "lakefile.toml").read_text(encoding="utf-8")
        manifest_bytes = (PROJECT / "lake-manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise LeanReferenceError(
            "E_TOOLCHAIN",
            "isolated Lean project lock is unavailable; run script/bootstrap_lean_reference.sh",
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
        toolchain != TOOLCHAIN
        or mathlib is None
        or mathlib.get("rev") != MATHLIB_REVISION
        or not revisions_are_exact
        or not lakefile_is_pinned
    ):
        raise LeanReferenceError(
            "E_TOOLCHAIN",
            "isolated Lean project does not match the pinned toolchain and Mathlib revision",
        )
    return {"manifestDigest": _digest_bytes(manifest_bytes)}


def _validate_kernel_output(value: bytes | str) -> None:
    # A theorem accepted through an admitted placeholder would not establish
    # the bound claim. The generated source never contains `sorry`; this check
    # also rejects a dependency path that leaked Lean's `sorryAx` into the
    # theorem's printed axioms.
    text = _bounded_text(value) if isinstance(value, bytes) else value
    if "...<truncated>" in text:
        raise LeanReferenceError("E_KERNEL", "Lean kernel output exceeded the supported limit")
    if "sorryAx" in text:
        raise LeanReferenceError("E_KERNEL", "Lean theorem depends on sorryAx")
    if len(_AXIOM_REPORT.findall(text)) != 1:
        raise LeanReferenceError("E_KERNEL", "Lean did not report the generated theorem's axioms")


def kernel_check(
    certificate: dict[str, Any],
    *,
    timeout_seconds: int = 180,
    lake: Path | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= 600
    ):
        raise LeanReferenceError("E_INPUT", "timeout-seconds must be between 1 and 600")
    source = build_lean_source(certificate)
    if lake is None:
        if not ELAN.is_file() or not os.access(ELAN, os.X_OK):
            raise LeanReferenceError(
                "E_TOOLCHAIN",
                "isolated Lean toolchain is unavailable; run script/bootstrap_lean_reference.sh",
            )
        checker = ELAN
        command_prefix = [str(ELAN), "run", TOOLCHAIN, "lake"]
    else:
        checker = lake.expanduser().resolve()
        if not checker.is_file() or not os.access(checker, os.X_OK):
            raise LeanReferenceError("E_TOOLCHAIN", f"Lake executable is unavailable: {checker}")
        command_prefix = [str(checker)]
    lock_metadata = _validate_project_lock()
    artifact_digest = _digest_bytes(source)
    environment = os.environ.copy()
    environment["ELAN_HOME"] = str(ELAN_HOME)
    runs_root = BUILD_ROOT / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="certificate-", dir=runs_root) as run_dir:
        source_path = Path(run_dir) / "MathAnchorCertificate.lean"
        source_path.write_bytes(source)
        completed = _run_bounded(
            [*command_prefix, "env", "lean", str(source_path)],
            cwd=PROJECT,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        raise LeanReferenceError("E_KERNEL", f"Lean rejected the generated theorem: {diagnostic}")
    kernel_output = f"{completed.stdout}\n{completed.stderr}"
    _validate_kernel_output(kernel_output)
    return {
        "status": "ok",
        "kind": "certificate_kernel_check",
        "assurance": "kernel_checked",
        "claim": "polynomial_identity_over_rationals",
        "scope": "bounded_translated_certificate_statement",
        "certificateDigest": certificate["certificateDigest"],
        "checkedBy": {
            "system": "lean4-kernel",
            "version": f"{TOOLCHAIN}+mathlib@{MATHLIB_REVISION}",
            "artifactDigest": artifact_digest,
            "checkerExecutableDigest": _digest_bytes(checker.read_bytes()),
            **lock_metadata,
        },
        "observations": {
            "kernelExitCode": completed.returncode,
            "kernelOutputDigest": _digest_bytes(kernel_output.encode("utf-8")),
            "kernelOutputTruncated": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check a Math Anchor polynomial certificate with Lean")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--source", help="certificate/result JSON file or - for stdin")
    sources.add_argument("--fixture", help="tracked research fixture id")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--lake",
        type=Path,
        help="explicit pinned Lake executable; the isolated Elan toolchain remains the default",
    )
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    try:
        if not 1 <= arguments.timeout_seconds <= 600:
            raise LeanReferenceError("E_INPUT", "timeout-seconds must be between 1 and 600")
        certificate = (
            _fixture_certificate(arguments.fixture)
            if arguments.fixture is not None
            else _load_json(arguments.source)
        )
        result = kernel_check(
            certificate,
            timeout_seconds=arguments.timeout_seconds,
            lake=arguments.lake,
        )
    except LeanReferenceError as error:
        result = {
            "status": "error",
            "error": {"code": error.code, "message": error.message},
            "checkedBy": None,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    if result["status"] == "error":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
