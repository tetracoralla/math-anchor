from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any


MANIFEST_NAME = ".math-anchor-build-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(bundle: Path) -> list[dict[str, Any]]:
    bundle_paths = sorted(bundle.rglob("*"))
    symlinks = [str(path.relative_to(bundle)) for path in bundle_paths if path.is_symlink()]
    if symlinks:
        raise SystemExit(
            "runtime bundle contains symbolic links that are not installation-stable: "
            + ", ".join(symlinks)
        )
    return [
        {
            "path": str(path.relative_to(bundle)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in bundle_paths
        if path.is_file() and path.name != MANIFEST_NAME
    ]


def source_digest(source_root: Path) -> str:
    source_files = sorted((source_root / "src" / "math_anchor").rglob("*.py"))
    source_files.extend(sorted((source_root / "legal").rglob("*")))
    source_files.extend(
        source_root / relative
        for relative in (
            "LICENSE",
            "NOTICE",
            "pyproject.toml",
            "requirements-runtime.lock",
            "script/package_runtime.sh",
            "script/generate_third_party_materials.py",
            "script/release_metadata.py",
            "script/runtime_manifest.py",
        )
    )
    digest = hashlib.sha256()
    for path in source_files:
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(source_root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def binary_architectures(runtime: Path) -> list[str]:
    result = subprocess.run(
        ["file", "-b", str(runtime)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    architectures = [name for name in ("arm64", "x86_64") if name in result]
    if not architectures:
        raise SystemExit(f"could not determine runtime architecture: {result.strip()}")
    return architectures


def write_manifest(bundle: Path, runtime: Path, lock: Path, source_root: Path, version: str) -> None:
    manifest = {
        "schemaVersion": 1,
        "productVersion": version,
        "platform": sys.platform,
        "buildArchitecture": platform.machine(),
        "runtimeArchitectures": binary_architectures(runtime),
        "pythonTag": sys.implementation.cache_tag,
        "pythonVersion": platform.python_version(),
        "runtimeLockSha256": sha256(lock),
        "sourceSha256": source_digest(source_root),
        "files": inventory(bundle),
    }
    (bundle / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_manifest(
    bundle: Path,
    runtime: Path,
    lock: Path,
    source_root: Path,
    version: str,
) -> None:
    manifest_path = bundle / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"runtime manifest is missing or invalid: {error}") from error
    expected_architecture = platform.machine()
    checks = {
        "schemaVersion": 1,
        "productVersion": version,
        "platform": sys.platform,
        "buildArchitecture": expected_architecture,
        "pythonTag": sys.implementation.cache_tag,
        "runtimeLockSha256": sha256(lock),
        "sourceSha256": source_digest(source_root),
    }
    for key, expected in checks.items():
        if manifest.get(key) != expected:
            raise SystemExit(f"runtime manifest mismatch for {key}: expected {expected!r}, found {manifest.get(key)!r}")
    actual_architectures = binary_architectures(runtime)
    if expected_architecture not in actual_architectures:
        raise SystemExit(
            f"runtime architecture mismatch: host is {expected_architecture}, binary has {actual_architectures}"
        )
    if manifest.get("runtimeArchitectures") != actual_architectures:
        raise SystemExit("runtime architecture does not match its build manifest")
    if manifest.get("files") != inventory(bundle):
        raise SystemExit("runtime file inventory does not match its build manifest")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "verify"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    runtime = arguments.runtime.resolve()
    lock = arguments.lock.resolve()
    source_root = arguments.source_root.resolve()
    if arguments.mode == "write":
        write_manifest(bundle, runtime, lock, source_root, arguments.version)
    else:
        verify_manifest(bundle, runtime, lock, source_root, arguments.version)


if __name__ == "__main__":
    main()
