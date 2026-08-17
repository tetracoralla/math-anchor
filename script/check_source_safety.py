from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "src" / "math_anchor"

FORBIDDEN_CALL = re.compile(r"(?<![A-Za-z0-9_])(?:eval|exec|sympify|parse_expr)\s*\(")
TOOL_NAME = re.compile(r'name="([^"]+)"')
EXPECTED_TOOLS = {"math.search", "math.describe", "math.run", "math.batch"}


def find_forbidden_calls(runtime: Path = RUNTIME) -> list[str]:
    violations: list[str] = []
    for path in sorted(runtime.rglob("*.py")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if FORBIDDEN_CALL.search(line):
                violations.append(f"{path.relative_to(runtime)}:{line_number}: {line.strip()}")
    return violations


def main() -> None:
    violations = find_forbidden_calls()

    if violations:
        joined = "\n".join(violations)
        raise SystemExit(f"Unsafe dynamic expression calls found:\n{joined}")

    mcp_source = (RUNTIME / "mcp_server.py").read_text()
    actual_tools = set(TOOL_NAME.findall(mcp_source))
    if actual_tools != EXPECTED_TOOLS:
        raise SystemExit(
            "MCP surface drifted: "
            f"expected {sorted(EXPECTED_TOOLS)}, found {sorted(actual_tools)}"
        )

    print("Source safety check passed: no dynamic evaluator calls; MCP surface remains exactly four tools.")


if __name__ == "__main__":
    main()
