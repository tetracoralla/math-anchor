#!/usr/bin/env python3
"""Verify that an installed Math Anchor Plugin is the exact packaged source artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


RUNTIME_MANIFEST = "runtime/math-anchor-runtime/.math-anchor-build-manifest.json"


def fail(message: str) -> None:
    raise SystemExit(f"Installed Plugin validation failed: {message}")


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        fail(f"could not read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"expected an object in {path}")
    return value


def load_server_object(source: str) -> dict[str, Any]:
    try:
        value = json.load(sys.stdin) if source == "-" else load_object(Path(source))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        fail(f"could not read the Codex MCP server JSON: {error}")
    if not isinstance(value, dict):
        fail("Codex MCP server JSON must be an object")
    return value


def inventory(root: Path) -> dict[str, tuple[str, bool]]:
    if not root.is_dir() or root.is_symlink():
        fail(f"Plugin root must be a real directory: {root}")
    output: dict[str, tuple[str, bool]] = {}
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in directory_names:
            candidate = directory_path / name
            if candidate.is_symlink():
                fail(f"Plugin directory contains a symbolic link: {candidate}")
        for name in file_names:
            candidate = directory_path / name
            if candidate.is_symlink() or not candidate.is_file():
                fail(f"Plugin entry must be a regular file: {candidate}")
            relative = candidate.relative_to(root).as_posix()
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            executable = bool(candidate.stat().st_mode & 0o111)
            output[relative] = (digest, executable)
    return output


def validate_server_route(installed: Path, server_value: dict[str, Any]) -> None:
    transport = server_value.get("transport")
    if (
        server_value.get("name") != "math-anchor"
        or server_value.get("enabled") is not True
        or not isinstance(transport, dict)
    ):
        fail(f"Math Anchor MCP is unavailable after installation: {server_value}")
    command_value = transport.get("command")
    if not isinstance(command_value, str) or not command_value:
        fail("Math Anchor MCP command is unavailable after installation")
    command = Path(command_value).expanduser()
    if command.is_absolute():
        executable = command.resolve()
    else:
        cwd_value = transport.get("cwd")
        if cwd_value is None:
            cwd = installed
        elif isinstance(cwd_value, str):
            candidate = Path(cwd_value).expanduser()
            cwd = candidate if candidate.is_absolute() else installed / candidate
        else:
            fail("Math Anchor MCP cwd has an invalid type")
        executable = (cwd / command).resolve()
    try:
        executable.relative_to(installed)
    except ValueError:
        fail(f"Codex MCP route escapes the installed Plugin root: {executable}")

    plugin_transport = load_object(installed / ".mcp.json")
    configured = plugin_transport.get("mcpServers", {}).get("math-anchor")
    if not isinstance(configured, dict):
        fail("installed Math Anchor MCP configuration is unavailable")
    configured_command = Path(str(configured.get("command", "")))
    configured_cwd = installed / str(configured.get("cwd", "."))
    expected_executable = (
        configured_command
        if configured_command.is_absolute()
        else configured_cwd / configured_command
    ).resolve()
    if executable != expected_executable:
        fail(
            "Codex MCP route does not match the installed Plugin manifest: "
            f"expected {expected_executable}, found {executable}"
        )
    if not executable.is_file() or not executable.stat().st_mode & 0o111:
        fail(f"Codex MCP executable is unavailable: {executable}")


def validate(
    source: Path,
    installed: Path,
    expected_version: str,
    server_value: dict[str, Any] | None = None,
) -> None:
    source = source.resolve()
    installed = installed.resolve()
    if source == installed:
        fail("source and installed Plugin roots must be distinct")

    source_inventory = inventory(source)
    installed_inventory = inventory(installed)
    if source_inventory != installed_inventory:
        missing = sorted(set(source_inventory) - set(installed_inventory))
        extra = sorted(set(installed_inventory) - set(source_inventory))
        changed = sorted(
            path
            for path in set(source_inventory) & set(installed_inventory)
            if source_inventory[path] != installed_inventory[path]
        )
        fail(
            "installed bytes differ from the packaged source "
            f"(missing={missing[:5]}, extra={extra[:5]}, changed={changed[:5]})"
        )

    for root in (source, installed):
        manifest = load_object(root / ".codex-plugin" / "plugin.json")
        if manifest.get("version") != expected_version:
            fail(
                f"Plugin manifest version mismatch in {root}: "
                f"expected {expected_version!r}, found {manifest.get('version')!r}"
            )
        runtime_manifest = load_object(root / RUNTIME_MANIFEST)
        if runtime_manifest.get("productVersion") != expected_version:
            fail(
                f"runtime version mismatch in {root}: "
                f"expected {expected_version!r}, found {runtime_manifest.get('productVersion')!r}"
            )
        transport = load_object(root / ".mcp.json")
        server = transport.get("mcpServers", {}).get("math-anchor")
        if not isinstance(server, dict):
            fail(f"math-anchor MCP server is missing in {root}")
        cwd = (root / str(server.get("cwd", ""))).resolve()
        command = Path(str(server.get("command", "")))
        executable = command if command.is_absolute() else cwd / command
        try:
            executable.resolve().relative_to(root)
        except ValueError:
            fail(f"MCP executable escapes the Plugin root in {root}")
        if not executable.is_file() or not executable.stat().st_mode & 0o111:
            fail(f"MCP executable is unavailable in {root}: {executable}")

    if server_value is not None:
        validate_server_route(installed, server_value)

    print(
        "Installed Plugin validation passed: "
        f"version {expected_version}, {len(source_inventory)} identical regular files"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plugin", required=True, type=Path)
    parser.add_argument("--installed-plugin", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--server-json")
    arguments = parser.parse_args()
    validate(
        arguments.source_plugin,
        arguments.installed_plugin,
        arguments.expected_version,
        load_server_object(arguments.server_json) if arguments.server_json else None,
    )


if __name__ == "__main__":
    main()
