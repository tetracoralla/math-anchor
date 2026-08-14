from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import platform
import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "zibetha"


def test_plugin_transport_stays_inside_the_plugin_bundle() -> None:
    config = json.loads((PLUGIN / ".mcp.json").read_text())
    server = config["mcpServers"]["zibetha"]
    cwd = (PLUGIN / server["cwd"]).resolve()
    executable = (cwd / server["command"]).resolve()

    assert cwd == PLUGIN.resolve()
    assert executable.is_relative_to(PLUGIN.resolve())


def test_app_packaging_copies_the_standalone_runtime() -> None:
    script = (ROOT / "script" / "build_and_run.sh").read_text()
    assert 'APP_RESOURCES="$APP_CONTENTS/Resources"' in script
    assert 'plugins/zibetha/runtime/zibetha-runtime' in script


def test_runtime_rebuild_check_ignores_generated_python_bytecode() -> None:
    script = (ROOT / "script" / "package_runtime.sh").read_text()
    assert "! -path '*/__pycache__/*'" in script
    assert "! -name '*.pyc'" in script


def test_generated_runtime_is_ignored_by_the_source_repository() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "plugins/zibetha/runtime/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--", "plugins/zibetha/runtime/**"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() == ""


def test_release_scripts_require_versioned_signed_notarized_artifacts() -> None:
    local_build = (ROOT / "script" / "build_and_run.sh").read_text()
    release = (ROOT / "script" / "release_macos.sh").read_text()
    assert "CFBundleShortVersionString" in local_build
    assert "CFBundleVersion" in local_build
    assert "--options runtime" in release
    assert "notarytool submit" in release
    assert "stapler validate" in release
    assert "spctl --assess" in release


def test_standalone_runtime_smoke_when_packaged_binary_exists() -> None:
    if os.environ.get("ZIBETHA_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    runtime = PLUGIN / "runtime" / "zibetha-runtime" / "zibetha-runtime"
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
    if os.environ.get("ZIBETHA_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    bundle = PLUGIN / "runtime" / "zibetha-runtime"
    runtime = bundle / "zibetha-runtime"
    manifest_path = bundle / ".zibetha-build-manifest.json"
    notice_path = bundle / "THIRD_PARTY_NOTICES.txt"
    sbom_path = bundle / "sbom.spdx.json"
    assert runtime.is_file()
    assert notice_path.stat().st_size > 10_000
    manifest = json.loads(manifest_path.read_text())
    assert manifest["buildArchitecture"] == platform.machine()
    assert platform.machine() in manifest["runtimeArchitectures"]
    assert any(item["path"] == "THIRD_PARTY_NOTICES.txt" for item in manifest["files"])
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
        "openssl",
        "xz utils liblzma",
        "mpdecimal",
    }
    assert packages["openssl"]["versionInfo"].startswith("3.")
    assert packages["openssl"]["licenseDeclared"] == "Apache-2.0"
    assert packages["xz utils liblzma"]["licenseDeclared"] == "0BSD"
    assert packages["mpdecimal"]["licenseDeclared"] == "BSD-2-Clause"
    assert all(package["licenseDeclared"] != "BSD" for package in packages.values())
    native_comments = "\n".join(
        package.get("comment", "") for package in packages.values()
    )
    for dylib in bundle.rglob("*.dylib"):
        assert str(dylib.relative_to(bundle)) in native_comments


def test_standalone_runtime_currency_uses_a_bundled_current_cache(tmp_path: Path) -> None:
    if os.environ.get("ZIBETHA_VERIFY_PACKAGED_RUNTIME") != "1":
        pytest.skip("packaged executables require the macOS runtime sandbox")
    runtime = PLUGIN / "runtime" / "zibetha-runtime" / "zibetha-runtime"
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
    environment["ZIBETHA_CURRENCY_CACHE_PATH"] = str(cache_path)
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
