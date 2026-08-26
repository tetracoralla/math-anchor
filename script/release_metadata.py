#!/usr/bin/env python3
"""Validate one product version across every distributable Math Anchor surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import re
import tomllib


MANIFEST_NAME = ".math-anchor-build-manifest.json"
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9]+)*$")


def fail(message: str) -> None:
    raise SystemExit(f"Release metadata validation failed: {message}")


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        fail(f"could not read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"expected an object in {path}")
    return value


def project_version(root: Path) -> str:
    project_path = root / "pyproject.toml"
    try:
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
        version = project["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        fail(f"could not read the project version from {project_path}: {error}")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        fail(f"invalid project version in {project_path}: {version!r}")
    return version


def canonical_version(root: Path) -> str:
    version = project_version(root)
    plugin_path = root / "plugins" / "math-anchor" / ".codex-plugin" / "plugin.json"
    plugin_version = load_json(plugin_path).get("version")
    if plugin_version != version:
        fail(
            "Plugin and Python project versions differ: "
            f"project={version!r}, plugin={plugin_version!r}"
        )
    package_path = root / "src" / "math_anchor" / "__init__.py"
    try:
        package_text = package_path.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"could not read the runtime package version from {package_path}: {error}")
    package_match = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', package_text, re.MULTILINE)
    package_version = package_match.group(1) if package_match else None
    if package_version != version:
        fail(
            "Python runtime and project versions differ: "
            f"project={version!r}, runtime={package_version!r}"
        )
    return version


def runtime_version(bundle: Path) -> str:
    manifest_path = bundle / MANIFEST_NAME
    value = load_json(manifest_path).get("productVersion")
    if not isinstance(value, str):
        fail(f"runtime productVersion is missing from {manifest_path}")
    return value


def app_metadata(app_bundle: Path) -> tuple[str, str]:
    plist_path = app_bundle / "Contents" / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        version = plist["CFBundleShortVersionString"]
        build = plist["CFBundleVersion"]
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        fail(f"could not read app release metadata from {plist_path}: {error}")
    if not isinstance(version, str) or not isinstance(build, str):
        fail(f"app version and build must be strings in {plist_path}")
    if not build.isdigit() or int(build) < 1:
        fail(f"app build must be a positive integer, found {build!r}")
    return version, build


def check_metadata(
    root: Path,
    runtime_bundles: list[Path],
    app_bundle: Path | None,
    expected_version: str | None,
    expected_build: str | None,
) -> str:
    version = canonical_version(root)
    if expected_version is not None and expected_version != version:
        fail(
            f"requested release version {expected_version!r} does not match "
            f"the canonical project version {version!r}"
        )
    for bundle in runtime_bundles:
        actual = runtime_version(bundle)
        if actual != version:
            fail(
                f"runtime version mismatch in {bundle}: "
                f"expected {version!r}, found {actual!r}"
            )
    if app_bundle is None:
        if expected_build is not None:
            fail("--expected-build requires --app-bundle")
        return version

    app_version, app_build = app_metadata(app_bundle)
    if app_version != version:
        fail(
            f"app version mismatch in {app_bundle}: "
            f"expected {version!r}, found {app_version!r}"
        )
    if expected_build is not None and app_build != expected_build:
        fail(
            f"app build mismatch in {app_bundle}: "
            f"expected {expected_build!r}, found {app_build!r}"
        )
    embedded_runtime = (
        app_bundle
        / "Contents"
        / "Resources"
        / "Runtime"
        / "math-anchor-runtime"
    )
    actual_runtime_version = runtime_version(embedded_runtime)
    if actual_runtime_version != version:
        fail(
            f"embedded runtime version mismatch in {app_bundle}: "
            f"expected {version!r}, found {actual_runtime_version!r}"
        )
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version")
    version_parser.add_argument("--root", required=True, type=Path)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--root", required=True, type=Path)
    check_parser.add_argument("--runtime-bundle", action="append", type=Path, default=[])
    check_parser.add_argument("--app-bundle", type=Path)
    check_parser.add_argument("--expected-version")
    check_parser.add_argument("--expected-build")

    arguments = parser.parse_args()
    root = arguments.root.resolve()
    if arguments.command == "version":
        print(canonical_version(root))
        return
    check_metadata(
        root,
        [bundle.resolve() for bundle in arguments.runtime_bundle],
        arguments.app_bundle.resolve() if arguments.app_bundle else None,
        arguments.expected_version,
        arguments.expected_build,
    )


if __name__ == "__main__":
    main()
