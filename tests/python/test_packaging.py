from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import platform
import shutil
import sys
import tomllib
import zipfile

from email.parser import BytesParser
from packaging.requirements import Requirement
from packaging.version import Version
import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "math-anchor"
GENERATED_OUTPUTS = (
    ".venv/",
    "plugins/math-anchor/runtime/",
    ".build/",
    ".swiftpm/",
    "build/",
    "dist/",
)

RUNTIME_MANIFEST_SPEC = importlib.util.spec_from_file_location(
    "math_anchor_runtime_manifest",
    ROOT / "script" / "runtime_manifest.py",
)
assert RUNTIME_MANIFEST_SPEC is not None and RUNTIME_MANIFEST_SPEC.loader is not None
runtime_manifest = importlib.util.module_from_spec(RUNTIME_MANIFEST_SPEC)
RUNTIME_MANIFEST_SPEC.loader.exec_module(runtime_manifest)

CHECK_PLUGIN_SPEC = importlib.util.spec_from_file_location(
    "math_anchor_check_plugin",
    ROOT / "script" / "check_plugin.py",
)
assert CHECK_PLUGIN_SPEC is not None and CHECK_PLUGIN_SPEC.loader is not None
check_plugin = importlib.util.module_from_spec(CHECK_PLUGIN_SPEC)
script_path = str(ROOT / "script")
sys.path.insert(0, script_path)
try:
    CHECK_PLUGIN_SPEC.loader.exec_module(check_plugin)
finally:
    sys.path.remove(script_path)


def _generated_gitignore() -> str:
    return "\n".join(GENERATED_OUTPUTS) + "\n"


def test_public_identity_uses_math_anchor_across_distribution_surfaces() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    transport = json.loads((PLUGIN / ".mcp.json").read_text())

    assert project["project"]["name"] == "math-anchor"
    assert Version(project["project"]["version"]) >= Version("0.2.0")
    assert set(project["project"]["scripts"]) == {"math-anchor", "math-anchor-mcp"}
    assert manifest["name"] == "math-anchor"
    assert manifest["version"] == project["project"]["version"]
    assert manifest["interface"]["displayName"] == "Math Anchor"
    assert set(transport["mcpServers"]) == {"math-anchor"}


def test_plugin_transport_stays_inside_the_plugin_bundle() -> None:
    config = json.loads((PLUGIN / ".mcp.json").read_text())
    server = config["mcpServers"]["math-anchor"]
    cwd = (PLUGIN / server["cwd"]).resolve()
    executable = (cwd / server["command"]).resolve()

    assert server["startup_timeout_sec"] == 30
    assert cwd == PLUGIN.resolve()
    assert executable.is_relative_to(PLUGIN.resolve())


def test_local_codex_marketplace_exposes_the_packaged_plugin() -> None:
    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert marketplace["name"] == "openadam"
    assert marketplace["plugins"] == [
        {
            "name": "math-anchor",
            "source": {"source": "local", "path": "./plugins/math-anchor"},
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            "category": "Productivity",
        }
    ]


def test_calculation_skill_keeps_cost_and_trust_boundaries() -> None:
    skill_path = PLUGIN / "skills" / "calculate" / "SKILL.md"
    skill = skill_path.read_text()
    assert len(skill.encode("utf-8")) <= 6_000
    assert "Do not load it for trivial, low-risk arithmetic" in skill
    assert "MUST load and use it for fixed-width" in skill
    assert "A successful tool response proves that the declared operation ran" in skill
    assert "Stop after the first successful call for an ordinary calculation" in skill
    assert "Never call `list_mcp_resources`" in skill
    assert "Use `dimension.check` for symbolic formula consistency" in skill
    assert "`dimension.pi_groups` for a Buckingham Pi basis" in skill
    assert "certificate.polynomial_identity" in skill
    assert "`checkedBy: null` means no checker" in skill
    assert "scope: dimensional_consistency_only" in skill
    assert "`precision` is not a top-level `math.run` field" in skill
    assert "at least two guard digits in the first call" in skill
    for reference in (
        "machine-semantics.md",
        "scientific-math.md",
        "statistics-units-dimensions.md",
        "result-error-policy.md",
    ):
        assert f"(references/{reference})" in skill
        assert (skill_path.parent / "references" / reference).is_file()
    agent_metadata = (
        PLUGIN / "skills" / "calculate" / "agents" / "openai.yaml"
    ).read_text()
    assert 'value: "math-anchor"' in agent_metadata


@pytest.mark.parametrize("entrypoint", ["check_all.sh", "package_runtime.sh"])
def test_build_entrypoints_pin_their_working_directory(entrypoint: str) -> None:
    script = (ROOT / "script" / entrypoint).read_text(encoding="utf-8")
    root_assignment = script.index('ROOT_DIR="$(cd ')
    pinned_working_directory = script.index('cd "$ROOT_DIR"')
    assert root_assignment < pinned_working_directory


def test_app_packaging_copies_the_standalone_runtime() -> None:
    script = (ROOT / "script" / "build_and_run.sh").read_text()
    assert 'APP_RESOURCES="$APP_CONTENTS/Resources"' in script
    assert 'plugins/math-anchor/runtime/math-anchor-runtime' in script


def test_runtime_rebuild_check_ignores_generated_python_bytecode() -> None:
    script = (ROOT / "script" / "package_runtime.sh").read_text()
    assert "! -path '*/__pycache__/*'" in script
    assert "! -name '*.pyc'" in script


def test_runtime_packaging_accepts_both_supported_python_loader_layouts() -> None:
    script = (ROOT / "script" / "package_runtime.sh").read_text()
    assert 'PYTHON_RUNTIME_LOADER="$PLUGIN_RUNTIME_BUNDLE/_internal/Python"' in script
    assert 'cp -pL "$PYTHON_RUNTIME_LOADER"' in script
    assert '[[ -L "$PYTHON_RUNTIME_LOADER" ]]' in script
    assert "-name 'libpython*.dylib'" in script
    assert '[[ "$python_loader_count" -eq 0 ]]' in script
    assert 'find "$PLUGIN_RUNTIME_BUNDLE" -type l' in script


def test_runtime_manifest_rejects_installer_unsafe_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("payload", encoding="utf-8")
    (tmp_path / "alias").symlink_to(target.name)

    with pytest.raises(SystemExit, match="not installation-stable"):
        runtime_manifest.inventory(tmp_path)


def test_runtime_manifest_does_not_hide_file_provider_conflict_copies(
    tmp_path: Path,
) -> None:
    (tmp_path / "LICENSE").write_text("current", encoding="utf-8")
    (tmp_path / "LICENSE 2").write_text("stale", encoding="utf-8")

    assert [item["path"] for item in runtime_manifest.inventory(tmp_path)] == [
        "LICENSE",
        "LICENSE 2",
    ]


@pytest.mark.parametrize(
    ("description", "expected"),
    (
        ("Mach-O universal binary with 2 architectures: [x86_64] [arm64]", ["arm64", "x86_64"]),
        ("ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV)", ["x86_64"]),
        ("ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV)", ["arm64"]),
    ),
)
def test_runtime_manifest_normalizes_supported_file_architecture_names(
    description: str,
    expected: list[str],
) -> None:
    assert runtime_manifest.architectures_from_file_output(description) == expected


@pytest.mark.parametrize(
    ("reported", "expected"),
    (
        ("aarch64", "arm64"),
        ("arm64", "arm64"),
        ("AMD64", "x86_64"),
        ("x86-64", "x86_64"),
        ("x86_64", "x86_64"),
    ),
)
def test_runtime_manifest_normalizes_supported_host_architecture_names(
    reported: str,
    expected: str,
) -> None:
    assert runtime_manifest.canonical_architecture(reported) == expected


def test_plugin_validation_consumes_the_complete_runtime_manifest(tmp_path: Path) -> None:
    # Negative regression: checking only that the executable existed allowed
    # File Provider conflict copies to pass plugin validation.
    bundle = tmp_path / "math-anchor-runtime"
    bundle.mkdir()
    executable = bundle / "math-anchor-runtime"
    shutil.copy2(sys.executable, executable)
    version = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    runtime_manifest.write_manifest(
        bundle=bundle,
        runtime=executable,
        lock=ROOT / "requirements-runtime.lock",
        source_root=ROOT,
        version=version,
    )

    check_plugin.validate_runtime_artifact(
        root=ROOT,
        executable=executable,
        version=version,
    )
    (bundle / "LICENSE 2").write_text("stale conflict copy", encoding="utf-8")
    with pytest.raises(SystemExit, match="runtime file inventory"):
        check_plugin.validate_runtime_artifact(
            root=ROOT,
            executable=executable,
            version=version,
        )


def test_bootstrap_rebuilds_a_file_provider_dataless_environment() -> None:
    script = (ROOT / "script" / "bootstrap.sh").read_text(encoding="utf-8")

    assert "venv_contains_dataless_files" in script
    assert "-flags +dataless" in script
    assert "File Provider-dataless generated .venv" in script


def test_python_resolver_canonicalizes_symlinked_interpreter_for_venv(
    tmp_path: Path,
) -> None:
    interpreter = Path(sys.executable).resolve()
    alias = tmp_path / "python3.11"
    alias.symlink_to(interpreter)
    command = (
        f'source "{ROOT / "script" / "python_env.sh"}"; '
        f'MATH_ANCHOR_PYTHON="{alias}"; '
        'resolve_math_anchor_python "for the resolver regression"; '
        'printf "%s" "$RESOLVED_MATH_ANCHOR_PYTHON"'
    )
    resolved = subprocess.run(
        ["/bin/bash", "-c", command],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert Path(resolved) == interpreter
    venv = tmp_path / "probe-venv"
    subprocess.run([resolved, "-m", "venv", str(venv)], check=True)
    subprocess.run(
        [str(venv / "bin" / "python"), "-c", "import encodings"],
        check=True,
    )


def test_bootstrap_recovers_an_unusable_generated_venv() -> None:
    script = (ROOT / "script" / "bootstrap.sh").read_text(encoding="utf-8")
    assert '"$PYTHON" -m venv --clear "$VENV_DIR"' in script


def test_bootstrap_uses_a_relocatable_noneditable_project_install() -> None:
    script = (ROOT / "script" / "bootstrap.sh").read_text(encoding="utf-8")
    assert "--force-reinstall" in script
    assert '"$ROOT_DIR"' in script
    assert "source.is_relative_to(venv)" in script
    assert " -e " not in script


def test_runtime_packaging_reinstalls_the_current_project_before_use() -> None:
    package_runtime = (ROOT / "script" / "package_runtime.sh").read_text(encoding="utf-8")
    check_all = (ROOT / "script" / "check_all.sh").read_text(encoding="utf-8")
    build_and_run = (ROOT / "script" / "build_and_run.sh").read_text(encoding="utf-8")
    assert '"$ROOT_DIR/script/bootstrap.sh"' in package_runtime
    assert '"$ROOT_DIR/script/package_runtime.sh"' in check_all
    assert '"$ROOT_DIR/script/package_runtime.sh"' in build_and_run


def test_generated_runtime_is_ignored_by_the_source_repository() -> None:
    checked = subprocess.run(
        [str(ROOT / "script" / "check_source_layout.sh"), "--development"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


@pytest.mark.parametrize(
    ("ignored_relative", "generated_relative"),
    [
        (".venv/", ".venv/generated"),
        ("plugins/math-anchor/runtime/", "plugins/math-anchor/runtime/binary"),
        (".build/", ".build/generated"),
        (".swiftpm/", ".swiftpm/generated"),
        ("build/", "build/generated"),
        ("dist/", "dist/generated"),
    ],
)
def test_source_layout_reports_each_tracked_or_unignored_generated_output(
    tmp_path: Path, ignored_relative: str, generated_relative: str
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "script" / "check_source_layout.sh", script_dir)
    shutil.copy2(ROOT / "script" / "validate_repo_paths.py", script_dir)
    shutil.copy2(ROOT / "script" / "python_env.sh", script_dir)

    def layout() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(script_dir / "check_source_layout.sh"), "--development"],
            cwd=archive,
            capture_output=True,
            text=True,
            check=False,
        )

    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "-q", str(archive)],
        capture_output=True,
        check=True,
    )
    ignored_outputs = list(GENERATED_OUTPUTS)
    (archive / ".gitignore").write_text(
        "\n".join(ignored_outputs) + "\n", encoding="utf-8"
    )
    generated = archive / generated_relative
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_bytes(b"generated")
    subprocess.run(
        ["git", "-C", str(archive), "add", "-f", generated_relative],
        capture_output=True,
        check=True,
    )

    tracked = layout()
    assert tracked.returncode != 0
    assert "Generated output must not be tracked by git" in tracked.stderr
    assert tracked.stderr.strip() != ""

    subprocess.run(
        [
            "git",
            "-C",
            str(archive),
            "rm",
            "-q",
            "--cached",
            generated_relative,
        ],
        capture_output=True,
        check=True,
    )
    assert layout().returncode == 0, layout().stderr

    (archive / ".gitignore").write_text(
        "\n".join(item for item in ignored_outputs if item != ignored_relative) + "\n",
        encoding="utf-8",
    )
    unignored = layout()
    assert unignored.returncode != 0
    assert f"Generated output must be ignored by git: {ignored_relative}" in unignored.stderr


def test_source_archive_without_git_metadata_has_an_equivalent_layout_check(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "script" / "check_source_layout.sh", script_dir)
    shutil.copy2(ROOT / "script" / "validate_repo_paths.py", script_dir)
    shutil.copy2(ROOT / "script" / "python_env.sh", script_dir)
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")

    clean = subprocess.run(
        [str(script_dir / "check_source_layout.sh"), "--archive-clean"],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert clean.returncode == 0, clean.stderr

    runtime = archive / "plugins" / "math-anchor" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "unexpected-binary").write_bytes(b"not source")
    development_checks = [
        subprocess.run(
            [str(script_dir / "check_source_layout.sh"), "--development"],
            cwd=archive,
            capture_output=True,
            text=True,
            check=False,
        )
        for _ in range(2)
    ]
    assert all(check.returncode == 0 for check in development_checks), [
        check.stderr for check in development_checks
    ]

    contaminated = subprocess.run(
        [str(script_dir / "check_source_layout.sh"), "--archive-clean"],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert contaminated.returncode != 0
    assert "must not contain generated output" in contaminated.stderr

    check_all = (ROOT / "script" / "check_all.sh").read_text(encoding="utf-8")
    assert '"$ROOT_DIR/script/check_source_layout.sh" --development' in check_all


@pytest.mark.parametrize("linked_component", ["plugins", "math-anchor", "runtime"])
def test_source_layout_rejects_every_runtime_symlink_ancestor(
    tmp_path: Path, linked_component: str
) -> None:
    archive = tmp_path / f"source-{linked_component}"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "script" / "check_source_layout.sh", script_dir)
    shutil.copy2(ROOT / "script" / "validate_repo_paths.py", script_dir)
    shutil.copy2(ROOT / "script" / "python_env.sh", script_dir)
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")

    external = tmp_path / f"external-{linked_component}"
    if linked_component == "plugins":
        (external / "math-anchor" / "runtime").mkdir(parents=True)
        (archive / "plugins").symlink_to(external, target_is_directory=True)
    elif linked_component == "math-anchor":
        (archive / "plugins").mkdir()
        (external / "runtime").mkdir(parents=True)
        (archive / "plugins" / "math-anchor").symlink_to(
            external, target_is_directory=True
        )
    else:
        (archive / "plugins" / "math-anchor").mkdir(parents=True)
        external.mkdir()
        (archive / "plugins" / "math-anchor" / "runtime").symlink_to(
            external, target_is_directory=True
        )

    checked = subprocess.run(
        [str(script_dir / "check_source_layout.sh"), "--development"],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode != 0
    assert "symbolic-link component" in checked.stderr


def test_package_runtime_refuses_parent_symlink_without_touching_external_files(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "script" / "package_runtime.sh", script_dir)
    shutil.copy2(ROOT / "script" / "validate_repo_paths.py", script_dir)
    shutil.copy2(ROOT / "script" / "python_env.sh", script_dir)

    external_runtime = tmp_path / "external-runtime"
    external_bundle = external_runtime / "math-anchor-runtime"
    external_bundle.mkdir(parents=True)
    sentinel = external_bundle / "keep-me"
    sentinel.write_text("outside repository", encoding="utf-8")
    plugin = archive / "plugins" / "math-anchor"
    plugin.mkdir(parents=True)
    (plugin / "runtime").symlink_to(external_runtime, target_is_directory=True)

    packaged = subprocess.run(
        [str(script_dir / "package_runtime.sh")],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert packaged.returncode != 0
    assert "symbolic-link component" in packaged.stderr
    assert sentinel.read_text(encoding="utf-8") == "outside repository"


def test_build_and_run_refuses_dist_symlink_before_replacing_the_app_bundle(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        "build_and_run.sh",
        "check_source_layout.sh",
        "swift_env.sh",
        "validate_repo_paths.py",
        "python_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)

    external_dist = tmp_path / "external-dist"
    external_app = external_dist / "Math Anchor.app"
    external_app.mkdir(parents=True)
    sentinel = external_app / "keep-me"
    sentinel.write_text("outside repository", encoding="utf-8")
    (archive / "dist").symlink_to(external_dist, target_is_directory=True)

    built = subprocess.run(
        [str(script_dir / "build_and_run.sh"), "--package"],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode != 0
    assert "symbolic-link component" in built.stderr
    assert sentinel.read_text(encoding="utf-8") == "outside repository"


@pytest.mark.parametrize("linked_output", [".build", ".swiftpm"])
def test_swift_env_refuses_generated_parent_symlink(
    tmp_path: Path, linked_output: str
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in ("swift_env.sh", "validate_repo_paths.py", "python_env.sh"):
        shutil.copy2(ROOT / "script" / name, script_dir)

    external_build = tmp_path / f"external-{linked_output.removeprefix('.')}"
    external_build.mkdir()
    (archive / linked_output).symlink_to(external_build, target_is_directory=True)

    configured = subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source script/swift_env.sh && configure_swift_environment "$PWD"',
        ],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert configured.returncode != 0
    assert "symbolic-link component" in configured.stderr
    assert list(external_build.iterdir()) == []


@pytest.mark.parametrize("external_exists", [False, True])
def test_bootstrap_refuses_symlinked_venv(
    tmp_path: Path, external_exists: bool
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        "bootstrap.sh",
        "validate_repo_paths.py",
        "python_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)

    external_venv = tmp_path / "external-venv"
    external_bin = external_venv / "bin"
    if external_exists:
        external_bin.mkdir(parents=True)
    marker = tmp_path / "external-venv-used"
    stub = external_bin / "python"
    if external_exists:
        stub.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 0\n', encoding="utf-8")
        stub.chmod(0o755)
    (archive / ".venv").symlink_to(external_venv, target_is_directory=True)

    bootstrapped = subprocess.run(
        [str(script_dir / "bootstrap.sh")],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bootstrapped.returncode != 0
    assert "symbolic-link component" in bootstrapped.stderr
    assert not marker.exists()


def test_release_hygiene_refuses_external_venv_before_executing_it(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        "check_release_hygiene.sh",
        "check_source_layout.sh",
        "validate_repo_paths.py",
        "python_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")

    external_venv = tmp_path / "external-venv"
    external_bin = external_venv / "bin"
    external_bin.mkdir(parents=True)
    marker = tmp_path / "external-python-ran"
    stub = external_bin / "python"
    stub.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n', encoding="utf-8")
    stub.chmod(0o755)
    (archive / ".venv").symlink_to(external_venv, target_is_directory=True)

    checked = subprocess.run(
        [str(script_dir / "check_release_hygiene.sh")],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode != 0
    assert "symbolic-link component" in checked.stderr
    assert not marker.exists()


def test_source_layout_does_not_execute_explicit_python_from_unsafe_venv(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        "check_source_layout.sh",
        "validate_repo_paths.py",
        "python_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")

    external_venv = tmp_path / "external-venv"
    external_bin = external_venv / "bin"
    external_bin.mkdir(parents=True)
    marker = tmp_path / "explicit-python-ran"
    stub = external_bin / "python"
    stub.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 0\n', encoding="utf-8")
    stub.chmod(0o755)
    (archive / ".venv").symlink_to(external_venv, target_is_directory=True)

    environment = os.environ.copy()
    environment["MATH_ANCHOR_PYTHON"] = str(archive / ".venv" / "bin" / "python")
    checked = subprocess.run(
        [str(script_dir / "check_source_layout.sh"), "--development"],
        cwd=archive,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode != 0
    assert "symbolic-link component" in checked.stderr
    assert not marker.exists()


@pytest.mark.parametrize("entrypoint", ["check_all.sh", "build_and_run.sh"])
def test_top_level_build_entrypoints_preflight_venv_before_any_build_output(
    tmp_path: Path, entrypoint: str
) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        entrypoint,
        "check_source_layout.sh",
        "validate_repo_paths.py",
        "python_env.sh",
        "swift_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")

    external_venv = tmp_path / "external-venv"
    external_venv.mkdir()
    (archive / ".venv").symlink_to(external_venv, target_is_directory=True)

    arguments = [str(script_dir / entrypoint)]
    if entrypoint == "build_and_run.sh":
        arguments.append("--package")
    checked = subprocess.run(
        arguments,
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode != 0
    assert "symbolic-link component" in checked.stderr
    assert not (archive / ".build").exists()
    assert not (archive / "dist").exists()
    assert list(external_venv.iterdir()) == []


def test_release_hygiene_reports_force_tracked_runtime(tmp_path: Path) -> None:
    archive = tmp_path / "math-anchor-source"
    script_dir = archive / "script"
    script_dir.mkdir(parents=True)
    for name in (
        "check_release_hygiene.sh",
        "check_source_layout.sh",
        "validate_repo_paths.py",
        "python_env.sh",
    ):
        shutil.copy2(ROOT / "script" / name, script_dir)

    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "-q", str(archive)],
        capture_output=True,
        check=True,
    )
    (archive / ".gitignore").write_text(_generated_gitignore(), encoding="utf-8")
    runtime = archive / "plugins" / "math-anchor" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "binary").write_bytes(b"generated")
    subprocess.run(
        ["git", "-C", str(archive), "add", "-f", "plugins/math-anchor/runtime/binary"],
        capture_output=True,
        check=True,
    )

    checked = subprocess.run(
        [str(script_dir / "check_release_hygiene.sh")],
        cwd=archive,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode != 0
    assert "Generated output must not be tracked by git" in checked.stderr


def test_build_and_test_requirements_exclude_the_reviewed_vulnerable_versions() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build_requirement = Requirement(project["build-system"]["requires"][0])
    pytest_requirement = next(
        Requirement(value)
        for value in project["project"]["optional-dependencies"]["dev"]
        if Requirement(value).name == "pytest"
    )

    assert Version("82.0.0") not in build_requirement.specifier
    assert Version("84.0.0") in build_requirement.specifier
    assert Version("9.0.2") not in pytest_requirement.specifier
    assert Version("9.0.3") in pytest_requirement.specifier


def test_wheel_uses_pep639_license_metadata_and_carries_legal_files(
    tmp_path: Path,
) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["license"] == "Apache-2.0"
    assert project["project"]["license-files"] == ["LICENSE", "NOTICE"]

    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(tmp_path),
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    wheel = next(tmp_path.glob("math_anchor-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        names = set(archive.namelist())

    assert metadata["License-Expression"] == "Apache-2.0"
    assert set(metadata.get_all("License-File", [])) == {"LICENSE", "NOTICE"}
    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    assert any(name.endswith(".dist-info/licenses/NOTICE") for name in names)


def test_github_ci_covers_both_supported_macos_architectures() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "runner: macos-15\n            architecture: arm64" in workflow
    assert "runner: macos-15-intel\n            architecture: x86_64" in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "persist-credentials: false" in workflow
    assert "timeout-minutes: 30" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "actions/checkout@v" not in workflow
    assert "actions/setup-python@v" not in workflow


def test_headless_distribution_covers_linux_wheel_sdist_and_non_root_oci() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    headless = (ROOT / "script" / "check_headless.sh").read_text(encoding="utf-8")
    build_lock = (ROOT / "requirements-build.lock").read_text(encoding="utf-8")

    assert "runner: ubuntu-24.04\n            architecture: x86_64" in workflow
    assert "runner: ubuntu-24.04-arm\n            architecture: arm64" in workflow
    assert "./script/check_headless.sh" in workflow
    assert "docker build --tag" in workflow
    assert "verify-certificate -" in workflow
    assert 'test "$(docker image inspect "$image" --format \'{{.Config.User}}\')" = "65532:65532"' in workflow

    pinned_base = (
        "python:3.11.16-slim-trixie@"
        "sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6"
    )
    assert dockerfile.count(f"FROM {pinned_base}") == 2
    assert "--require-hashes --requirement requirements-build.lock" in dockerfile
    assert "--require-hashes --requirement requirements-runtime.lock" in dockerfile
    assert "USER 65532:65532" in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "math_anchor.mcp_server"]' in dockerfile
    assert "setuptools==84.0.0" in build_lock and "--hash=sha256:" in build_lock

    for command in (
        "-m pytest",
        "check_source_safety.py",
        "check_mcp.py",
        "load_check.py",
        "build_python_dist.py\" build",
        "build_python_dist.py\" verify",
    ):
        assert command in headless
    assert "check_mcp.py\" --source-runtime" in headless

    assert "name: release-python" in release
    assert "build/python-dist/math_anchor-*.whl" in release
    assert "build/python-dist/math_anchor-*.tar.gz" in release
    assert "needs: [python-dist, signed-macos]" in release


def test_github_release_requires_signed_notarized_assets_from_both_architectures() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "runner: macos-15\n            architecture: arm64" in workflow
    assert "runner: macos-15-intel\n            architecture: x86_64" in workflow
    assert "persist-credentials: false" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in workflow
    assert "APPLE_DEVELOPER_ID_P12_BASE64" in workflow
    assert "APPLE_NOTARY_PRIVATE_KEY_BASE64" in workflow
    assert 'export MATH_ANCHOR_NOTARY_KEYCHAIN="$keychain_path"' in workflow
    assert "./script/release_macos.sh" in workflow
    assert "sha256sum --check" in workflow
    assert "gh release create" in workflow
    assert "--clobber" not in workflow
    assert "Refusing to replace assets on existing release" in workflow


def test_signed_release_refreshes_embedded_materials_after_nested_signing() -> None:
    script = (ROOT / "script" / "release_macos.sh").read_text(encoding="utf-8")
    nested_signing = script.index('done < <(find "$APP_BUNDLE/Contents" -type f -print0)')
    regenerate_sbom = script.index('"$ROOT_DIR/script/generate_third_party_materials.py"', nested_signing)
    rewrite_manifest = script.index('"$ROOT_DIR/script/runtime_manifest.py" write', regenerate_sbom)
    outer_signing = script.index('codesign --force --timestamp --options runtime --sign "$SIGNING_IDENTITY" "$APP_BUNDLE"')

    assert nested_signing < regenerate_sbom < rewrite_manifest < outer_signing
    assert 'cp "$APP_RUNTIME_BUNDLE/sbom.spdx.json" "$SBOM"' in script
    assert 'shasum -a 256 "${ARCHIVE##*/}"' in script


def test_release_workflow_gates_signing_on_green_ci_and_checksums_the_sbom() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    script = (ROOT / "script" / "release_macos.sh").read_text(encoding="utf-8")

    # Negative regression: signing must fail closed unless the tagged commit's
    # CI runs are green, and must never publish a checksum-less SBOM.
    gate_step = workflow.index("Require green CI on the tagged commit")
    bootstrap = workflow.index("./script/bootstrap.sh", gate_step)
    assert gate_step < bootstrap
    assert "actions: read" in workflow
    assert "timeout-minutes: 90" in workflow
    assert "compare/${GITHUB_SHA}...${default_branch}" in workflow
    assert "not contained in ${default_branch}" in workflow
    assert "repos/${GITHUB_REPOSITORY}/actions/runs?head_sha=${GITHUB_SHA}" in workflow
    assert "refusing to sign" in workflow

    assert 'SBOM_CHECKSUM="$SBOM.sha256"' in script
    assert 'shasum -a 256 "${SBOM##*/}"' in script
    assert 'dist/Math-Anchor-*-${{ matrix.architecture }}.spdx.json.sha256' in workflow
    assert "release-assets/*.sha256" in workflow
    assert "release-assets/*.zip.sha256" not in workflow


def test_release_scripts_require_versioned_signed_notarized_artifacts() -> None:
    local_build = (ROOT / "script" / "build_and_run.sh").read_text()
    release = (ROOT / "script" / "release_macos.sh").read_text()
    assert "CFBundleShortVersionString" in local_build
    assert "CFBundleVersion" in local_build
    assert 'APP_DISPLAY_NAME="Math Anchor"' in local_build
    assert 'APP_EXECUTABLE="MathAnchor"' in local_build
    assert "--options runtime" in release
    assert "notarytool submit" in release
    assert 'NOTARY_KEYCHAIN="${MATH_ANCHOR_NOTARY_KEYCHAIN:-}"' in release
    assert 'NOTARY_ARGUMENTS+=(--keychain "$NOTARY_KEYCHAIN")' in release
    assert "stapler validate" in release
    assert "spctl --assess" in release
    assert "check_release_source.sh" in release
    assert 'MATH_ANCHOR_APP_VERSION="$VERSION"' in release
    assert 'MATH_ANCHOR_BUILD_NUMBER="$BUILD_NUMBER"' in release


def test_public_repository_has_contribution_and_report_routes() -> None:
    required = [
        ROOT / "CONTRIBUTING.md",
        ROOT / "CODE_OF_CONDUCT.md",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
        ROOT / ".github" / "pull_request_template.md",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in required)
    bug_report = required[2].read_text(encoding="utf-8")
    issue_config = required[4].read_text(encoding="utf-8")
    assert "private vulnerability" in bug_report.lower()
    assert "security/advisories/new" in issue_config


def test_standalone_runtime_smoke_when_packaged_binary_exists() -> None:
    if os.environ.get("MATH_ANCHOR_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    runtime = PLUGIN / "runtime" / "math-anchor-runtime" / "math-anchor-runtime"
    if not runtime.is_file():
        return
    completed = subprocess.run(
        [str(runtime), "app"],
        input='{"id":"packaged","expression":"6*7","precision":16}\n',
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert json.loads(lines[0]) == {"status": "ready"}
    assert json.loads(lines[1])["exact"] == "42"


def test_packaged_runtime_has_matching_manifest_notices_and_sbom() -> None:
    if os.environ.get("MATH_ANCHOR_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    bundle = PLUGIN / "runtime" / "math-anchor-runtime"
    runtime = bundle / "math-anchor-runtime"
    manifest_path = bundle / ".math-anchor-build-manifest.json"
    project_license_path = bundle / "LICENSE"
    project_notice_path = bundle / "NOTICE"
    notice_path = bundle / "THIRD_PARTY_NOTICES.txt"
    sbom_path = bundle / "sbom.spdx.json"
    assert runtime.is_file()
    loaders = [
        path
        for path in (
            bundle / "_internal" / "Python",
            *(bundle / "_internal").rglob("libpython*.dylib"),
        )
        if path.is_file()
    ]
    assert loaders
    assert all(not loader.is_symlink() for loader in loaders)
    assert not any(path.is_symlink() for path in bundle.rglob("*"))
    assert project_license_path.read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert project_notice_path.read_bytes() == (ROOT / "NOTICE").read_bytes()
    assert notice_path.stat().st_size > 10_000
    manifest = json.loads(manifest_path.read_text())
    host_architecture = runtime_manifest.canonical_architecture(platform.machine())
    assert manifest["buildArchitecture"] == host_architecture
    assert host_architecture in manifest["runtimeArchitectures"]
    manifest_paths = {item["path"] for item in manifest["files"]}
    assert {"LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.txt", "sbom.spdx.json"} <= manifest_paths
    sbom = json.loads(sbom_path.read_text())
    assert sbom["spdxVersion"] == "SPDX-2.3"
    packages = {package["name"].lower(): package for package in sbom["packages"]}
    assert set(packages) >= {
        "python",
        "sympy",
        "numpy",
        "mpmath",
        "pint",
        "psutil",
        "mcp",
        "pyinstaller bootloader",
    }
    assert all(
        package["licenseDeclared"] != "NOASSERTION"
        for package in packages.values()
    )
    for name in ("flexcache", "mpmath", "pint", "sympy"):
        assert packages[name]["licenseDeclared"] == "BSD-3-Clause"
    # Native-library components depend on how the build interpreter links
    # OpenSSL/lzma/mpdecimal: statically linked interpreters (GitHub-hosted
    # toolcache builds) bundle no standalone dylibs for them, while Homebrew
    # interpreters do. The environment-independent invariant is coverage:
    # every third-party dylib actually present in the bundle must be claimed
    # by an SBOM component, and libpython belongs to the Python component.
    claimed = {
        file
        for package in sbom["packages"]
        for file in _bundled_files_from_comment(package.get("comment"))
    }
    for path in sorted((bundle / "_internal").rglob("*.dylib")):
        relative = str(path.relative_to(bundle))
        assert relative in claimed, f"unclaimed bundled dylib: {relative}"


def _bundled_files_from_comment(comment: object) -> list[str]:
    if not isinstance(comment, str) or not comment.startswith("Bundled files: "):
        return []
    return [
        item.strip() for item in comment[len("Bundled files: ") :].split(", ")
    ]


def test_standalone_runtime_currency_uses_a_bundled_current_cache(tmp_path: Path) -> None:
    if os.environ.get("MATH_ANCHOR_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    runtime = PLUGIN / "runtime" / "math-anchor-runtime" / "math-anchor-runtime"
    if not runtime.is_file():
        return

    checked_at = datetime.now(timezone.utc)
    cache_path = tmp_path / "ecb-rates.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "provider": "ECB",
                "rateDate": checked_at.date().isoformat(),
                "publishedAt": checked_at.isoformat().replace("+00:00", "Z"),
                "checkedAt": checked_at.isoformat().replace("+00:00", "Z"),
                "expiresAt": (checked_at + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                "rates": {
                    "EUR": "1",
                    "USD": "1.1545",
                    "JPY": "171.82",
                    "CZK": "24.365",
                    "DKK": "7.4681",
                    "GBP": "0.87010",
                    "HUF": "395.18",
                    "PLN": "4.2430",
                    "RON": "5.0807",
                    "SEK": "11.0690",
                    "CHF": "0.9435",
                    "ISK": "143.50",
                    "NOK": "11.8160",
                    "TRY": "53.0120",
                    "AUD": "1.7815",
                    "BRL": "6.2620",
                    "CAD": "1.5846",
                    "CNY": "8.2205",
                    "HKD": "9.0165",
                    "INR": "104.98"
                },
            }
        )
    )
    environment = os.environ.copy()
    environment["MATH_ANCHOR_CURRENCY_CACHE_PATH"] = str(cache_path)
    completed = subprocess.run(
        [str(runtime), "app"],
        input=(
            '{"id":"currency","operation":"currency.convert",'
            '"value":"100","fromCurrency":"USD","toCurrency":"EUR",'
            '"precision":12}\n'
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=environment,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert json.loads(lines[0]) == {"status": "ready"}
    result = json.loads(lines[1])
    assert result["status"] == "ok"
    assert result["operation"] == "currency.convert"
    assert result["rate"]["sourceShortName"] == "ECB"
    assert result["rate"]["state"] == "current"
    assert result["rate"]["isCached"] is True


def test_unit_registries_are_lazy_for_cold_start() -> None:
    # Negative regression: constructing the pint registries parses the full
    # unit definition file (~150 ms) and must not happen at import time,
    # or every worker, app, and MCP cold start pays it.
    code = (
        "import math_anchor.operations.data as data\n"
        "assert data._EXACT_UNIT_REGISTRY is None, 'exact registry built at import'\n"
        "assert data._FLOAT_UNIT_REGISTRY is None, 'float registry built at import'\n"
        "from math_anchor.runtime import execute_direct\n"
        "result = execute_direct('units.convert', "
        "{'value': '1', 'fromUnit': 'meter', 'toUnit': 'centimeter'})\n"
        "assert result['exact'] == '100', result\n"
        "assert data._EXACT_UNIT_REGISTRY is not None, 'registry missing after first use'\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert completed.returncode == 0, completed.stderr
