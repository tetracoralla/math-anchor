from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, source: str) -> None:
    path.write_text(source)
    path.chmod(0o755)


def test_explicit_sdk_override_is_selected_before_discovery(tmp_path: Path) -> None:
    explicit_sdk = tmp_path / "MacOSX15.4.sdk"
    discovered_sdk = tmp_path / "MacOSX26.5.sdk"
    explicit_sdk.mkdir()
    discovered_sdk.mkdir()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(fake_bin / "swiftc", "#!/bin/sh\nexit 0\n")
    _write_executable(
        fake_bin / "xcrun",
        f"#!/bin/sh\nprintf '%s\\n' '{discovered_sdk}'\n",
    )

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["MATH_ANCHOR_SDKROOT"] = str(explicit_sdk)
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source script/swift_env.sh; configure_swift_environment "$PWD"; printf "%s" "$SDKROOT"',
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == str(explicit_sdk)


def test_invalid_explicit_sdk_does_not_fall_back_to_discovery(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(fake_bin / "swiftc", "#!/bin/sh\nexit 0\n")
    _write_executable(fake_bin / "xcrun", "#!/bin/sh\nexit 0\n")

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["MATH_ANCHOR_SDKROOT"] = str(tmp_path / "missing.sdk")
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source script/swift_env.sh; configure_swift_environment "$PWD"',
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "Explicit macOS SDK does not exist" in completed.stderr
