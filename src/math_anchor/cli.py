from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from .errors import CalculatorError, error_payload
from .output_policy import DEFAULT_MAX_OUTPUT_BYTES
from .transport_budget import MAX_BATCH_REQUEST_BYTES


MAX_CERTIFICATE_INPUT_BYTES = 1_048_576


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CalculatorError("E_INPUT", message)


def _json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("arguments JSON must be an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = StructuredArgumentParser(prog="math-anchor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search the operation catalog")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--category")

    describe = subparsers.add_parser("describe", help="Describe one operation")
    describe.add_argument("operation")

    run = subparsers.add_parser("run", help="Run one isolated operation")
    run.add_argument("operation")
    run.add_argument("arguments", type=_json_object)
    run.add_argument("--timeout-ms", type=int, default=10_000)
    run.add_argument("--memory-mb", type=int, default=2048)
    run.add_argument("--result-mode", choices=("auto", "exact", "approx", "both"), default="auto")
    run.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES)

    batch = subparsers.add_parser("batch", help="Run an array of isolated operations")
    batch.add_argument("items", help="JSON array or - to read JSON from stdin")

    verify = subparsers.add_parser(
        "verify-certificate",
        help="Independently verify a Math Anchor certificate JSON object",
    )
    verify.add_argument("source", help="Certificate/result JSON file or - for stdin")

    verify_lean = subparsers.add_parser(
        "verify-certificate-lean",
        help="Check a true polynomial identity certificate with the Lean kernel",
    )
    verify_lean.add_argument("source", help="Certificate/result JSON file or - for stdin")
    verify_lean.add_argument("--lake", required=True, type=Path)
    verify_lean.add_argument("--project", required=True, type=Path)
    verify_lean.add_argument("--artifact-output", type=Path)
    verify_lean.add_argument("--timeout", type=int, default=120)

    obligation_schema = subparsers.add_parser(
        "obligation-schema",
        help="Print the versioned obligation request, receipt, or feedback schema",
    )
    obligation_schema.add_argument(
        "kind",
        choices=("request", "receipt", "feedback"),
    )

    check_obligations = subparsers.add_parser(
        "check-obligations",
        help="Check one bounded obligation set for a local Agent Host or harness",
    )
    check_obligations.add_argument("source", help="Obligation-set JSON file or - for stdin")
    check_obligations.add_argument(
        "--receipt-output",
        type=Path,
        help="Write the full replayable receipt to a new file",
    )
    check_obligations.add_argument(
        "--quiet-success",
        action="store_true",
        help="Emit nothing when every obligation is checked",
    )

    replay_obligations = subparsers.add_parser(
        "replay-obligations",
        help="Re-run an obligation set and compare it with a prior full receipt",
    )
    replay_obligations.add_argument("request", help="Obligation-set JSON file or - for stdin")
    replay_obligations.add_argument("receipt", help="Prior full receipt JSON file")
    replay_obligations.add_argument(
        "--receipt-output",
        type=Path,
        help="Write the current full receipt to a new file",
    )
    return parser


def _batch_items(raw: str) -> list[dict[str, Any]]:
    if raw == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        encoded = stream.read(MAX_BATCH_REQUEST_BYTES + 1)
        encoded_bytes = (
            encoded.encode("utf-8") if isinstance(encoded, str) else encoded
        )
        if len(encoded_bytes) > MAX_BATCH_REQUEST_BYTES:
            raise CalculatorError(
                "E_LIMIT",
                f"batch input may contain at most {MAX_BATCH_REQUEST_BYTES} bytes",
            )
        try:
            source = encoded_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CalculatorError("E_INPUT", f"invalid batch JSON: {error}") from error
    else:
        source = raw
    value = json.loads(source)
    if not isinstance(value, list):
        raise CalculatorError("E_INPUT", "batch input must be an array")
    return value


def _certificate_value(source: str) -> dict[str, Any]:
    if source == "-":
        raw = sys.stdin.buffer.read(MAX_CERTIFICATE_INPUT_BYTES + 1)
    else:
        try:
            with Path(source).open("rb") as handle:
                raw = handle.read(MAX_CERTIFICATE_INPUT_BYTES + 1)
        except OSError as error:
            raise CalculatorError(
                "E_INPUT",
                f"certificate file could not be read: {error}",
            ) from error
    if len(raw) > MAX_CERTIFICATE_INPUT_BYTES:
        raise CalculatorError(
            "E_LIMIT",
            f"certificate input may contain at most {MAX_CERTIFICATE_INPUT_BYTES} bytes",
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise CalculatorError("E_INPUT", f"invalid certificate JSON: {error}") from error
    if not isinstance(value, dict):
        raise CalculatorError("E_INPUT", "certificate JSON must be an object")
    if "certificate" in value:
        nested = value["certificate"]
        if not isinstance(nested, dict):
            raise CalculatorError("E_INPUT", "result certificate must be an object")
        return nested
    return value


def _json_document(source: str, *, maximum_bytes: int, label: str) -> dict[str, Any]:
    if source == "-":
        raw = sys.stdin.buffer.read(maximum_bytes + 1)
    else:
        try:
            with Path(source).open("rb") as handle:
                raw = handle.read(maximum_bytes + 1)
        except OSError as error:
            raise CalculatorError("E_INPUT", f"{label} file could not be read: {error}") from error
    if len(raw) > maximum_bytes:
        raise CalculatorError(
            "E_LIMIT",
            f"{label} input may contain at most {maximum_bytes} bytes",
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise CalculatorError("E_INPUT", f"invalid {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise CalculatorError("E_INPUT", f"{label} JSON must be an object")
    return value


def _write_new_json(path: Path, value: dict[str, Any], *, label: str) -> None:
    temporary_path: Path | None = None
    try:
        encoded = (
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # A same-directory hard link publishes the complete bytes atomically
        # and fails rather than replacing an existing receipt.
        os.link(temporary_path, path)
    except FileExistsError as error:
        raise CalculatorError("E_INPUT", f"{label} already exists; refusing to overwrite it") from error
    except OSError as error:
        raise CalculatorError("E_INPUT", f"{label} could not be written: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = build_parser()
    exit_code = 0
    emit = True
    try:
        arguments = parser.parse_args()
        if arguments.command == "search":
            from .catalog import search_operations

            result = search_operations(arguments.query, arguments.category)
        elif arguments.command == "describe":
            from .catalog import describe_operation

            result = describe_operation(arguments.operation)
        elif arguments.command == "run":
            from .sandbox import run_operation

            result = run_operation(
                arguments.operation,
                arguments.arguments,
                timeout_ms=arguments.timeout_ms,
                memory_mb=arguments.memory_mb,
                result_mode=arguments.result_mode,
                max_output_bytes=arguments.max_output_bytes,
            )
        elif arguments.command == "batch":
            from .sandbox import run_batch

            result = run_batch(_batch_items(arguments.items))
        elif arguments.command == "verify-certificate":
            from .certificate_checker import (
                CertificateValidationError,
                verify_polynomial_identity_certificate,
            )

            try:
                check = verify_polynomial_identity_certificate(
                    _certificate_value(arguments.source)
                )
            except CertificateValidationError as error:
                raise CalculatorError("E_CERTIFICATE", str(error)) from error
            result = {
                "status": "ok",
                "kind": "certificate_check",
                **check,
            }
        elif arguments.command == "verify-certificate-lean":
            from .certificate_checker import CertificateValidationError
            from .lean_bridge import verify_polynomial_identity_with_lean

            try:
                result = verify_polynomial_identity_with_lean(
                    _certificate_value(arguments.source),
                    lake=arguments.lake,
                    project_root=arguments.project,
                    artifact_output=arguments.artifact_output,
                    timeout=arguments.timeout,
                )
            except CertificateValidationError as error:
                raise CalculatorError("E_CERTIFICATE", str(error)) from error
        elif arguments.command == "obligation-schema":
            from .obligations import (
                obligation_feedback_schema,
                obligation_receipt_schema,
                obligation_request_schema,
            )

            result = {
                "request": obligation_request_schema,
                "receipt": obligation_receipt_schema,
                "feedback": obligation_feedback_schema,
            }[arguments.kind]()
        elif arguments.command == "check-obligations":
            from .obligations import (
                MAX_OBLIGATION_REQUEST_BYTES,
                check_obligation_set,
            )

            request = _json_document(
                arguments.source,
                maximum_bytes=MAX_OBLIGATION_REQUEST_BYTES,
                label="obligation request",
            )
            result, receipt = check_obligation_set(request)
            if arguments.receipt_output is not None:
                _write_new_json(arguments.receipt_output, receipt, label="receipt output")
            if result["status"] == "attention_required":
                exit_code = 1
            elif arguments.quiet_success:
                emit = False
        else:
            from .obligations import (
                MAX_OBLIGATION_REQUEST_BYTES,
                MAX_RECEIPT_BYTES,
                replay_obligation_set,
            )

            request = _json_document(
                arguments.request,
                maximum_bytes=MAX_OBLIGATION_REQUEST_BYTES,
                label="obligation request",
            )
            previous_receipt = _json_document(
                arguments.receipt,
                maximum_bytes=MAX_RECEIPT_BYTES,
                label="obligation receipt",
            )
            result, _feedback, receipt = replay_obligation_set(request, previous_receipt)
            if arguments.receipt_output is not None:
                _write_new_json(arguments.receipt_output, receipt, label="receipt output")
            if result["status"] != "matched":
                exit_code = 1
    except CalculatorError as error:
        result = {"status": "error", "error": error.as_dict()}
        exit_code = 2
    except json.JSONDecodeError as error:
        result = {"status": "error", "error": error_payload("E_INPUT", f"invalid JSON: {error}")}
        exit_code = 2
    if result.get("status") == "error":
        exit_code = 2
    if emit:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
