from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "math-anchor"


def fail(message: str) -> None:
    raise SystemExit(f"Plugin validation failed: {message}")


def main() -> None:
    manifest_path = PLUGIN / ".codex-plugin" / "plugin.json"
    transport_path = PLUGIN / ".mcp.json"
    if not manifest_path.is_file() or not transport_path.is_file():
        fail("manifest and MCP transport files are required")

    manifest = json.loads(manifest_path.read_text())
    for key in ("name", "version", "description", "license", "skills", "mcpServers"):
        if not manifest.get(key):
            fail(f"manifest field {key!r} is required")
    if manifest["name"] != "math-anchor":
        fail("manifest name must remain math-anchor")
    if manifest["mcpServers"] != "./.mcp.json":
        fail("manifest must point to the repository MCP transport")

    transport = json.loads(transport_path.read_text())
    server = transport.get("mcpServers", {}).get("math-anchor")
    if not isinstance(server, dict):
        fail("math-anchor MCP server is required")
    cwd = (PLUGIN / server.get("cwd", "")).resolve()
    command = Path(server.get("command", ""))
    executable = command if command.is_absolute() else cwd / command
    if cwd != PLUGIN.resolve():
        fail("MCP working directory must remain inside the installed plugin")
    try:
        executable.resolve().relative_to(PLUGIN.resolve())
    except ValueError:
        fail("MCP command must remain inside the installed plugin")
    if not executable.is_file():
        fail(f"MCP command does not exist: {executable}")
    if not executable.stat().st_mode & 0o111:
        fail(f"MCP command is not executable: {executable}")

    skills_root = PLUGIN / manifest["skills"]
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        fail("at least one product Skill is required")
    frontmatter = re.compile(r"^---\nname:\s*\S+\ndescription:\s*.+?\n---\n", re.DOTALL)
    for skill_file in skill_files:
        if not frontmatter.match(skill_file.read_text()):
            fail(f"invalid Skill frontmatter: {skill_file.relative_to(ROOT)}")

    print(f"Plugin validation passed: {PLUGIN}")


if __name__ == "__main__":
    main()
