from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "math_anchor_release_metadata",
    ROOT / "script" / "release_metadata.py",
)
assert SPEC is not None and SPEC.loader is not None
release_metadata = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_metadata
SPEC.loader.exec_module(release_metadata)


def write_project(root: Path, project_version: str, plugin_version: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "math-anchor"\nversion = "{project_version}"\n',
        encoding="utf-8",
    )
    plugin = root / "plugins" / "math-anchor" / ".codex-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps({"name": "math-anchor", "version": plugin_version}),
        encoding="utf-8",
    )


def write_runtime(bundle: Path, version: str) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / release_metadata.MANIFEST_NAME).write_text(
        json.dumps({"productVersion": version}),
        encoding="utf-8",
    )


def write_app(app: Path, app_version: str, build: str, runtime_version: str) -> None:
    contents = app / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleShortVersionString": app_version,
                "CFBundleVersion": build,
            },
            handle,
        )
    write_runtime(
        contents / "Resources" / "Runtime" / "math-anchor-runtime",
        runtime_version,
    )


def test_canonical_version_rejects_plugin_drift(tmp_path: Path) -> None:
    write_project(tmp_path, "0.1.0", "0.2.0")

    with pytest.raises(SystemExit, match="Plugin and Python project versions differ"):
        release_metadata.canonical_version(tmp_path)


def test_release_metadata_accepts_one_consistent_version(tmp_path: Path) -> None:
    write_project(tmp_path, "0.1.0", "0.1.0")
    plugin_runtime = tmp_path / "plugins" / "math-anchor" / "runtime-bundle"
    app = tmp_path / "dist" / "Math Anchor.app"
    write_runtime(plugin_runtime, "0.1.0")
    write_app(app, "0.1.0", "7", "0.1.0")

    assert (
        release_metadata.check_metadata(
            tmp_path,
            [plugin_runtime],
            app,
            expected_version="0.1.0",
            expected_build="7",
        )
        == "0.1.0"
    )


@pytest.mark.parametrize(
    ("app_version", "runtime_version", "message"),
    [
        ("9.9.9", "0.1.0", "app version mismatch"),
        ("0.1.0", "9.9.9", "embedded runtime version mismatch"),
    ],
)
def test_release_metadata_rejects_mismatched_app_or_runtime(
    tmp_path: Path, app_version: str, runtime_version: str, message: str
) -> None:
    write_project(tmp_path, "0.1.0", "0.1.0")
    app = tmp_path / "dist" / "Math Anchor.app"
    write_app(app, app_version, "1", runtime_version)

    with pytest.raises(SystemExit, match=message):
        release_metadata.check_metadata(tmp_path, [], app, None, None)


def test_release_metadata_rejects_requested_version_or_build_drift(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, "0.1.0", "0.1.0")
    app = tmp_path / "dist" / "Math Anchor.app"
    write_app(app, "0.1.0", "1", "0.1.0")

    with pytest.raises(SystemExit, match="requested release version"):
        release_metadata.check_metadata(tmp_path, [], app, "0.2.0", None)
    with pytest.raises(SystemExit, match="app build mismatch"):
        release_metadata.check_metadata(tmp_path, [], app, "0.1.0", "2")


def run_source_check(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["MATH_ANCHOR_APP_VERSION"] = "0.1.0"
    return subprocess.run(
        ["/bin/bash", str(root / "script" / "check_release_source.sh")],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_signed_release_requires_clean_exact_annotated_tag(tmp_path: Path) -> None:
    write_project(tmp_path, "0.1.0", "0.1.0")
    script = tmp_path / "script"
    script.mkdir()
    for name in ("check_release_source.sh", "python_env.sh", "release_metadata.py"):
        shutil.copy2(ROOT / "script" / name, script / name)
    (tmp_path / "README.md").write_text("release fixture\n", encoding="utf-8")
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "-q"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Math Anchor Tests"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "release fixture"],
        cwd=tmp_path,
        check=True,
    )

    untagged = run_source_check(tmp_path)
    assert untagged.returncode != 0
    assert "annotated tag v0.1.0" in untagged.stderr

    subprocess.run(["git", "tag", "v0.1.0"], cwd=tmp_path, check=True)
    lightweight = run_source_check(tmp_path)
    assert lightweight.returncode != 0
    assert "v0.1.0 to be an annotated tag" in lightweight.stderr
    subprocess.run(["git", "tag", "-d", "v0.1.0"], cwd=tmp_path, check=True)

    subprocess.run(
        ["git", "tag", "-a", "v0.1.0", "-m", "Math Anchor 0.1.0"],
        cwd=tmp_path,
        check=True,
    )
    clean = run_source_check(tmp_path)
    assert clean.returncode == 0, clean.stderr

    (tmp_path / "README.md").write_text("dirty release fixture\n", encoding="utf-8")
    dirty = run_source_check(tmp_path)
    assert dirty.returncode != 0
    assert "clean Git worktree and index" in dirty.stderr
