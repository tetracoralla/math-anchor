from __future__ import annotations

import os
import sys


def _restore_stream(stream_name: str) -> None:
    stream = getattr(sys, stream_name, None)
    if stream is None or getattr(stream, "closed", False):
        descriptor = 1 if stream_name == "stdout" else 2
        setattr(sys, stream_name, open(descriptor, "w", closefd=False))


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "app":
        from math_anchor.app_runtime import main as app_main
        try:
            app_main()
        finally:
            _restore_stream("stdout")
            _restore_stream("stderr")
        return
    if mode == "mcp":
        from math_anchor.mcp_server import main as mcp_main

        original_stdin = sys.stdin
        original_stdout = sys.stdout
        duplicated_stdin = os.fdopen(os.dup(original_stdin.fileno()), "r", encoding="utf-8", errors="replace")
        duplicated_stdout = os.fdopen(os.dup(original_stdout.fileno()), "w", encoding="utf-8")
        sys.stdin = duplicated_stdin
        sys.stdout = duplicated_stdout
        try:
            mcp_main()
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout
            _restore_stream("stdout")
            _restore_stream("stderr")
        return
    if mode == "worker":
        _restore_stream("stdout")
        _restore_stream("stderr")
        from math_anchor.worker import main as worker_main

        worker_main()
        return
    if mode in {
        "obligation-schema",
        "check-obligations",
        "replay-obligations",
        "verify-certificate",
        "verify-certificate-lean",
    }:
        _restore_stream("stdout")
        _restore_stream("stderr")
        from math_anchor.cli import main as cli_main

        cli_main()
        return
    raise SystemExit(
        "usage: math-anchor-runtime app|mcp|obligation-schema|check-obligations|"
        "replay-obligations|verify-certificate|verify-certificate-lean"
    )


if __name__ == "__main__":
    main()
