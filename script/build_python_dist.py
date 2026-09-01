from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "python-dist"


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _ensure_generated_path(path: Path) -> None:
    resolved_root = ROOT.resolve()
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(resolved_root / "build"):
        raise SystemExit(f"refusing generated path outside build: {resolved}")


def _checksum(path: Path) -> Path:
    digest = sha256(path.read_bytes()).hexdigest()
    checksum = path.with_name(f"{path.name}.sha256")
    checksum.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return checksum


def build() -> list[Path]:
    _ensure_generated_path(DIST)
    DIST.mkdir(parents=True, exist_ok=True)
    from setuptools import build_meta

    previous_directory = Path.cwd()
    try:
        os.chdir(ROOT)
        wheel_name = build_meta.build_wheel(str(DIST))
        sdist_name = build_meta.build_sdist(str(DIST))
    finally:
        os.chdir(previous_directory)
    artifacts = [DIST / wheel_name, DIST / sdist_name]
    for artifact in artifacts:
        _checksum(artifact)
    return artifacts


def _only_artifact(suffix: str) -> Path:
    prefix = f"math_anchor-{_project_version()}"
    matches = sorted(
        path
        for path in DIST.iterdir()
        if path.name.startswith(prefix) and path.name.endswith(suffix)
    )
    if len(matches) != 1:
        raise SystemExit(f"expected one Math Anchor {suffix} artifact, found {len(matches)}")
    return matches[0]


def _verify_checksum(artifact: Path) -> None:
    checksum = artifact.with_name(f"{artifact.name}.sha256")
    expected_line = f"{sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}\n"
    if not checksum.is_file() or checksum.read_text(encoding="utf-8") != expected_line:
        raise SystemExit(f"checksum mismatch for {artifact.name}")


def _verify_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        required_suffixes = {
            ".dist-info/METADATA",
            ".dist-info/licenses/LICENSE",
            ".dist-info/licenses/NOTICE",
        }
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                raise SystemExit(f"wheel is missing {suffix}")
        required_modules = {
            "math_anchor/certificate_checker.py",
            "math_anchor/operations/certificate.py",
            "math_anchor/research_contract.py",
        }
        if not required_modules <= set(names):
            raise SystemExit("wheel is missing research-runtime modules")
        if any("__pycache__" in name or name.endswith(".pyc") for name in names):
            raise SystemExit("wheel contains generated Python cache files")


def _verify_sdist(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        names = [PurePosixPath(member.name) for member in archive.getmembers()]
    if not any(path.name == "LICENSE" for path in names):
        raise SystemExit("source distribution is missing LICENSE")
    if not any(path.name == "NOTICE" for path in names):
        raise SystemExit("source distribution is missing NOTICE")
    forbidden = {".venv", ".build", ".swiftpm", "build", "dist", "runtime", "__pycache__"}
    if any(forbidden.intersection(path.parts) for path in names):
        raise SystemExit("source distribution contains generated output")


def _wheel_smoke(wheel: Path) -> None:
    smoke_parent = ROOT / "build"
    _ensure_generated_path(smoke_parent)
    smoke_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="python-wheel-smoke-",
        dir=smoke_parent,
    ) as temporary_target:
        smoke_target = Path(temporary_target)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--target",
                str(smoke_target),
                str(wheel),
            ],
            check=True,
        )
        smoke = (
            "from math_anchor.runtime import execute_direct\n"
            "from math_anchor.certificate_checker import verify_polynomial_identity_certificate\n"
            "result = execute_direct('certificate.polynomial_identity', "
            "{'left': '(x+1)^2', 'right': 'x^2+2*x+1', 'variables': ['x']})\n"
            "assert verify_polynomial_identity_certificate(result['certificate'])['valid']\n"
        )
        environment = {**dict(os.environ), "PYTHONPATH": str(smoke_target)}
        completed = subprocess.run(
            [sys.executable, "-c", smoke],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(f"wheel smoke failed: {completed.stderr.strip()}")


def verify() -> list[Path]:
    if not DIST.is_dir():
        raise SystemExit("python distribution directory does not exist")
    wheel = _only_artifact("-py3-none-any.whl")
    sdist = _only_artifact(".tar.gz")
    for artifact in (wheel, sdist):
        _verify_checksum(artifact)
    _verify_wheel(wheel)
    _verify_sdist(sdist)
    _wheel_smoke(wheel)
    return [wheel, sdist]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify Math Anchor Python distributions")
    parser.add_argument("command", choices=("build", "verify"))
    arguments = parser.parse_args()
    artifacts = build() if arguments.command == "build" else verify()
    for artifact in artifacts:
        print(artifact)


if __name__ == "__main__":
    main()
