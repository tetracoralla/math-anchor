from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess
import tempfile

from runtime_manifest import verify_manifest


ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "math-anchor"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
HOST_PLUGIN = ROOT / "integrations" / "agent-host" / "plugin.json"
HOST_INTEGRATION = ROOT / "integrations" / "agent-host" / "tool.integration.json"


def fail(message: str) -> None:
    raise SystemExit(f"Plugin validation failed: {message}")


def validate_runtime_artifact(*, root: Path, executable: Path, version: str) -> None:
    try:
        verify_manifest(
            bundle=executable.parent,
            runtime=executable,
            lock=root / "requirements-runtime.lock",
            source_root=root,
            version=version,
        )
    except SystemExit as error:
        fail(f"runtime artifact is invalid: {error}")


def validate_obligation_runtime(executable: Path, version: str) -> None:
    version_result = subprocess.run(
        [str(executable), "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if version_result.returncode != 0 or version_result.stdout.strip() != version:
        fail("packaged obligation launcher did not report the project version")
    request = {
        "schemaVersion": "math-anchor.obligation-set.v0.1",
        "obligations": [
            {
                "id": "packaged-identity",
                "kind": "polynomial_identity",
                "claim": {
                    "left": "(x + 1)^2",
                    "right": "x^2 + 2*x + 1",
                    "variables": ["x"],
                },
            }
        ],
    }
    with tempfile.TemporaryDirectory(prefix="math-anchor-obligation-check-") as temporary:
        receipt = Path(temporary) / "receipt.json"
        completed = subprocess.run(
            [
                str(executable),
                "check-obligations",
                "-",
                "--receipt-output",
                str(receipt),
                "--quiet-success",
            ],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0 or completed.stdout:
            fail(
                "packaged obligation runtime did not complete silently: "
                f"exit={completed.returncode} stderr={completed.stderr[-240:]}"
            )
        if not receipt.is_file():
            fail("packaged obligation runtime did not write a receipt")
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != "math-anchor.obligation-receipt.v0.1":
            fail("packaged obligation runtime wrote an incompatible receipt")
        if value.get("summary", {}).get("checked") != 1:
            fail("packaged obligation runtime did not check the smoke obligation")


def validate_host_obligation_route(version: str) -> None:
    plugin = json.loads(HOST_PLUGIN.read_text(encoding="utf-8"))
    integration = json.loads(HOST_INTEGRATION.read_text(encoding="utf-8"))
    if plugin.get("version") != version:
        fail("Agent Host plugin version does not match the project")
    if integration.get("schemaVersion") != "openadam.agent-host-tool-integration.v0.3":
        fail("Agent Host obligation route must use the Skill CLI integration")
    runtime = integration.get("runtime")
    discovery = integration.get("discovery")
    if not isinstance(runtime, dict) or not isinstance(discovery, dict):
        fail("Agent Host runtime and obligation discovery route are required")
    skill = discovery.get("skill")
    discovery_runtime = discovery.get("runtime")
    if not isinstance(skill, dict) or not isinstance(discovery_runtime, dict):
        fail("Agent Host obligation Skill and packaged runtime are required")
    expected_command = runtime.get("command")
    if discovery.get("kind") != "skill-cli":
        fail("Agent Host obligation route must be a Host-projected Skill CLI")
    if skill != {
        "id": "calculate",
        "root": "marketplace/plugins/math-anchor-obligation-runtime/skills/calculate",
        "identityFiles": ["SKILL.md"],
        "launcher": "scripts/math-anchor",
    }:
        fail("Agent Host obligation Skill binding is incompatible")
    if discovery_runtime != {
        "executor": "component",
        "command": expected_command,
        "args": [],
        "versionArguments": ["--version"],
    }:
        fail("Agent Host obligation launcher is not version-locked to the packaged runtime")
    skill_text = (PLUGIN / "skills" / "calculate" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "`scripts/math-anchor` launcher",
        "`check-obligations` or `replay-obligations`",
        "Never substitute an ambient command or source checkout",
    ):
        if required not in skill_text:
            fail("calculate Skill does not route obligations through the Host launcher")


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
    if server.get("startup_timeout_sec") != 30:
        fail("MCP cold-start timeout must remain explicitly bounded at 30 seconds")
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
    validate_runtime_artifact(
        root=ROOT,
        executable=executable,
        version=str(manifest["version"]),
    )
    validate_obligation_runtime(executable, str(manifest["version"]))
    validate_host_obligation_route(str(manifest["version"]))

    skills_root = PLUGIN / manifest["skills"]
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        fail("at least one product Skill is required")
    frontmatter = re.compile(r"^---\nname:\s*\S+\ndescription:\s*.+?\n---\n", re.DOTALL)
    for skill_file in skill_files:
        skill_text = skill_file.read_text()
        if not frontmatter.match(skill_text):
            fail(f"invalid Skill frontmatter: {skill_file.relative_to(ROOT)}")

    calculate_skill = PLUGIN / "skills" / "calculate" / "SKILL.md"
    calculate_text = calculate_skill.read_text()
    if len(calculate_text.encode("utf-8")) > 6_000:
        fail("calculate Skill must stay below the 6 KB always-loaded budget")
    reference_paths = set(re.findall(r"\]\((references/[^)]+\.md)\)", calculate_text))
    expected_references = {
        "references/machine-semantics.md",
        "references/scientific-math.md",
        "references/statistics-units-dimensions.md",
        "references/result-error-policy.md",
    }
    if reference_paths != expected_references:
        fail("calculate Skill must link the complete bounded reference set")
    for relative_path in reference_paths:
        if not (calculate_skill.parent / relative_path).is_file():
            fail(f"calculate Skill reference is missing: {relative_path}")
    if "Do not load it for trivial, low-risk arithmetic" not in calculate_text:
        fail("calculate Skill must preserve the trivial-arithmetic routing boundary")
    if "A successful tool response proves that the declared operation ran" not in calculate_text:
        fail("calculate Skill must distinguish execution success from correct problem translation")
    if "Stop after the first successful call for an ordinary calculation" not in calculate_text:
        fail("calculate Skill must reject duplicate calls as fake validation")
    if "`precision` is not a top-level `math.run` field" not in calculate_text:
        fail("calculate Skill must place precision inside operation arguments")
    if "at least two guard digits in the first call" not in calculate_text:
        fail("calculate Skill must avoid a second call for decimal-place rounding")
    if "Use `dimension.check` for symbolic formula consistency" not in calculate_text:
        fail("calculate Skill must route symbolic dimensional checks separately from quantities")
    if "`dimension.pi_groups` for a Buckingham Pi basis" not in calculate_text:
        fail("calculate Skill must route dimensionless-group requests directly")
    if "scope: dimensional_consistency_only" not in calculate_text:
        fail("calculate Skill must preserve the dimensional-analysis claim boundary")
    agent_metadata = calculate_skill.parent / "agents" / "openai.yaml"
    if not agent_metadata.is_file():
        fail("calculate Skill must declare its Math Anchor MCP dependency")
    metadata_text = agent_metadata.read_text()
    if 'value: "math-anchor"' not in metadata_text:
        fail("calculate Skill MCP dependency must name math-anchor")

    if not MARKETPLACE.is_file():
        fail("local Codex marketplace manifest is required")
    marketplace = json.loads(MARKETPLACE.read_text())
    if marketplace.get("name") != "openadam":
        fail("local marketplace name must remain openadam")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        fail("local marketplace must expose exactly one plugin")
    entry = entries[0]
    if entry.get("name") != "math-anchor":
        fail("local marketplace plugin name must remain math-anchor")
    source = entry.get("source")
    if source != {"source": "local", "path": "./plugins/math-anchor"}:
        fail("local marketplace must point to the bundled math-anchor plugin")

    print(f"Plugin validation passed: {PLUGIN}")


if __name__ == "__main__":
    main()
