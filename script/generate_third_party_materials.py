from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import fnmatch
import hashlib
from importlib.metadata import (
    PackageNotFoundError,
    distribution,
    distributions,
)
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, Callable, Iterable

from packaging.markers import Marker, default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


LOCK_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")
HASH_PATTERN = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")
LICENSE_NAMES = ("license", "copying", "notice", "copyright")
VALID_LICENSE_EXPRESSIONS = {
    "0BSD",
    "Apache-2.0",
    "Apache-2.0 OR BSD-3-Clause",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
    "GPL-2.0-or-later WITH Bootloader-exception",
    "ISC",
    "MIT",
    "MPL-2.0",
    "NOASSERTION",
    "PSF-2.0",
    "X11",
}
LEGACY_LICENSE_NORMALIZATION = {
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD License": "NOASSERTION",
    "BSD": "NOASSERTION",
    "MIT License": "MIT",
}
DECLARED_LICENSE_OVERRIDES = {
    # These releases publish the ambiguous legacy metadata value "BSD", but
    # their bundled license files contain the three-clause BSD text. Keep the
    # override version-specific so a dependency update must be re-reviewed.
    ("flexcache", "0.3"): "BSD-3-Clause",
    ("mpmath", "1.3.0"): "BSD-3-Clause",
    ("pint", "0.25.3"): "BSD-3-Clause",
    ("sympy", "1.14.0"): "BSD-3-Clause",
}


@dataclass(frozen=True)
class BundledComponent:
    name: str
    version: str
    license_declared: str
    download_location: str
    notice_texts: tuple[tuple[str, str], ...]
    bundled_files: tuple[str, ...]


@dataclass(frozen=True)
class NativeDefinition:
    name: str
    file_patterns: tuple[str, ...]
    version_pattern: bytes
    license_declared: str
    download_location: str
    license_paths: tuple[str, ...]


NATIVE_DEFINITIONS = (
    NativeDefinition(
        name="OpenSSL",
        file_patterns=("libssl.*.dylib", "libcrypto.*.dylib"),
        version_pattern=rb"OpenSSL ([0-9]+\.[0-9]+\.[0-9]+)",
        license_declared="Apache-2.0",
        download_location="https://www.openssl.org/source/",
        license_paths=("LICENSE",),
    ),
    NativeDefinition(
        name="XZ Utils liblzma",
        file_patterns=("liblzma.*.dylib",),
        version_pattern=rb"(?<![0-9])(5\.[0-9]+\.[0-9]+)(?![0-9])",
        license_declared="0BSD",
        download_location="https://tukaani.org/xz/",
        license_paths=("legal/native/liblzma-0BSD.txt",),
    ),
    NativeDefinition(
        name="mpdecimal",
        file_patterns=("libmpdec.*.dylib",),
        version_pattern=rb"(?<![0-9])(4\.[0-9]+\.[0-9]+)(?![0-9])",
        license_declared="BSD-2-Clause",
        download_location="https://www.bytereef.org/mpdecimal/",
        license_paths=("legal/native/mpdecimal-BSD-2-Clause.txt",),
    ),
    NativeDefinition(
        # GitHub-hosted CPython links the system editline, which pulls in
        # ncurses; PyInstaller then bundles it into the runtime. The version
        # is the ABI major embedded in the dylib's install name, the only
        # stable identifier across the build origins that ship this library.
        name="ncurses",
        file_patterns=("libncurses*.dylib",),
        version_pattern=rb"libncursesw?\.([0-9]+)\.dylib",
        license_declared="X11",
        download_location="https://invisible-island.net/ncurses/",
        license_paths=("legal/native/ncurses-X11.txt",),
    ),
)


def locked_packages(path: Path) -> list[tuple[str, str]]:
    packages: list[tuple[str, str]] = []
    seen: set[str] = set()
    logical_lines: list[tuple[int, str]] = []
    pending_parts: list[str] = []
    pending_start = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or (line.startswith("#") and not pending_parts):
            continue
        if not pending_parts:
            pending_start = line_number
        continued = line.endswith("\\")
        pending_parts.append(line[:-1].strip() if continued else line)
        if continued:
            continue
        logical_lines.append((pending_start, " ".join(pending_parts)))
        pending_parts = []
    if pending_parts:
        raise SystemExit(f"unterminated locked requirement at {path}:{pending_start}")

    for line_number, logical_line in logical_lines:
        parts = logical_line.split()
        match = LOCK_PATTERN.fullmatch(parts[0])
        if match is None:
            raise SystemExit(
                f"invalid locked requirement at {path}:{line_number}: {logical_line}"
            )
        hashes = parts[1:]
        if not hashes or any(HASH_PATTERN.fullmatch(value) is None for value in hashes):
            raise SystemExit(
                f"locked requirement has missing or invalid sha256 hashes at "
                f"{path}:{line_number}: {parts[0]}"
            )
        normalized = canonicalize_name(match.group(1))
        if normalized in seen:
            raise SystemExit(
                f"duplicate locked package at {path}:{line_number}: {parts[0]}"
            )
        seen.add(normalized)
        packages.append((match.group(1), match.group(2)))
    if not packages:
        raise SystemExit(f"dependency lock is empty: {path}")
    return packages


def _marker_applies(marker: Marker | None, extras: Iterable[str]) -> bool:
    if marker is None:
        return True
    active_extras = {"", *(extra.lower() for extra in extras)}
    for extra in active_extras:
        environment = default_environment()
        environment["extra"] = extra
        if marker.evaluate(environment):
            return True
    return False


def _marker_applies_supported(marker: Marker | None, extras: Iterable[str]) -> bool:
    """Return whether a dependency applies to a supported macOS/Linux build."""
    if marker is None:
        return True
    active_extras = {"", *(extra.lower() for extra in extras)}
    base = default_environment()
    platforms = (
        ("darwin", "posix", "Darwin"),
        ("linux", "posix", "Linux"),
    )
    machines = ("arm64", "aarch64", "x86_64")
    for sys_platform, os_name, platform_system in platforms:
        for platform_machine in machines:
            for extra in active_extras:
                environment = dict(base)
                environment.update(
                    {
                        "sys_platform": sys_platform,
                        "os_name": os_name,
                        "platform_system": platform_system,
                        "platform_machine": platform_machine,
                        "extra": extra,
                    }
                )
                if marker.evaluate(environment):
                    return True
    return False


def _dependency_closure(
    requirements: Iterable[str],
    marker_applies: Callable[[Marker | None, Iterable[str]], bool],
) -> dict[str, str]:
    closure: dict[str, str] = {}
    processed: set[tuple[str, tuple[str, ...]]] = set()
    pending = [Requirement(value) for value in requirements]
    while pending:
        requested = pending.pop()
        normalized = canonicalize_name(requested.name)
        active_extras = tuple(sorted(extra.lower() for extra in requested.extras))
        request_key = (normalized, active_extras)
        if request_key in processed:
            continue
        processed.add(request_key)
        try:
            installed = distribution(requested.name)
        except PackageNotFoundError as error:
            raise SystemExit(
                f"project dependency is not installed: {requested.name}"
            ) from error
        if requested.specifier and not requested.specifier.contains(
            installed.version, prereleases=True
        ):
            raise SystemExit(
                f"installed dependency does not satisfy {requested}: "
                f"found {installed.version}"
            )
        existing_version = closure.get(normalized)
        if existing_version is not None and existing_version != installed.version:
            raise SystemExit(
                f"dependency closure contains conflicting versions for {requested.name}"
            )
        closure[normalized] = installed.version
        for raw_requirement in installed.requires or []:
            requirement = Requirement(raw_requirement)
            if marker_applies(requirement.marker, active_extras):
                pending.append(requirement)
    return closure


def validate_dependency_closure(
    project_path: Path,
    packages: list[tuple[str, str]],
    *,
    project_extras: Iterable[str] = (),
) -> dict[str, str]:
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    requirements = list(project["project"].get("dependencies", []))
    optional = project["project"].get("optional-dependencies", {})
    for extra in project_extras:
        if extra not in optional:
            raise SystemExit(f"unknown project extra: {extra}")
        requirements.extend(optional[extra])

    closure = _dependency_closure(requirements, _marker_applies)
    supported_closure = _dependency_closure(requirements, _marker_applies_supported)

    locked = {canonicalize_name(name): version for name, version in packages}
    missing = sorted(set(closure) - set(locked))
    extra = sorted(set(locked) - set(supported_closure))
    drift = sorted(
        name
        for name in set(supported_closure) & set(locked)
        if supported_closure[name] != locked[name]
    )
    if missing or extra or drift:
        raise SystemExit(
            "dependency lock does not match the installed project dependency closure; "
            f"missing={missing}, extra={extra}, versionDrift={drift}"
        )
    return closure


def license_files(package_name: str) -> tuple[Any, list[Path]]:
    try:
        installed = distribution(package_name)
    except PackageNotFoundError as error:
        raise SystemExit(f"bundled package is not installed: {package_name}") from error
    candidates: list[Path] = []
    for item in installed.files or []:
        filename = item.name.lower()
        if not filename.startswith(LICENSE_NAMES):
            continue
        located = Path(installed.locate_file(item))
        if located.is_file():
            candidates.append(located)
    unique = sorted(set(candidates), key=lambda path: str(path))
    if not unique:
        raise SystemExit(f"no license material found for bundled package: {package_name}")
    return installed, unique


def python_license() -> Path:
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        for candidate in (parent / "LICENSE", parent / "LICENSE.txt"):
            if candidate.is_file():
                return candidate
    # CPython's `make install` places the license in the stdlib directory
    # instead of the prefix root, so hosted runner Pythons (GitHub's
    # toolcache builds) carry it only under lib/pythonX.Y.
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for root in (Path(sys.prefix), Path(getattr(sys, "base_prefix", sys.prefix))):
        for candidate in (root / "lib" / version / "LICENSE.txt", root / "lib" / version / "LICENSE"):
            if candidate.is_file():
                return candidate
    raise SystemExit("could not locate the license for the Python runtime")


def safe_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def spdx_id(name: str) -> str:
    return "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", name)


def declared_license(installed: Any) -> str:
    package_key = (
        canonicalize_name(installed.metadata.get("Name", "")),
        installed.version,
    )
    override = DECLARED_LICENSE_OVERRIDES.get(package_key)
    if override is not None:
        return override
    expression = installed.metadata.get("License-Expression")
    legacy = installed.metadata.get("License")
    candidate = expression or LEGACY_LICENSE_NORMALIZATION.get(legacy, legacy)
    if candidate in VALID_LICENSE_EXPRESSIONS:
        return candidate
    return "NOASSERTION"


def _archive_top_level_modules(runtime: Path, bundle: Path) -> set[str]:
    try:
        from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    except ImportError as error:
        raise SystemExit("PyInstaller is required to inventory the bundled runtime") from error

    archive = CArchiveReader(str(runtime))
    pyz_entry = archive.toc.get("PYZ.pyz")
    if pyz_entry is None:
        raise SystemExit("bundled runtime does not contain a PYZ archive")
    pyz = ZlibArchiveReader(
        str(runtime),
        start_offset=archive._start_offset + pyz_entry[0],
    )
    top_levels = {name.split(".", 1)[0] for name in pyz.toc}
    internal = bundle / "_internal"
    for path in internal.rglob("*.so"):
        relative = path.relative_to(internal)
        if len(relative.parts) > 1:
            top_levels.add(relative.parts[0])
        else:
            top_levels.add(path.name.split(".", 1)[0])
    return top_levels


def _inferred_top_levels(files: Iterable[Path]) -> set[str]:
    """Infer top-level module names from a distribution's installed files.

    Some bundled distributions (numpy, pint, mcp) ship no top_level.txt,
    and the stdlib packages_distributions() fallback for those arrived
    only in later 3.11 patch releases, so this generator must not depend
    on the interpreter patch version to see them.
    """
    tops: set[str] = set()
    for item in files:
        parts = item.parts
        if not parts or not str(item).endswith((".py", ".so")):
            continue
        head = parts[0]
        if head.endswith((".dist-info", ".egg-info", ".data")):
            continue
        tops.add(head.rsplit(".", 1)[0] if len(parts) == 1 else head)
    return tops


def _module_to_distributions() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for dist in distributions():
        declared = dist.read_text("top_level.txt")
        names = (
            [line.strip() for line in declared.splitlines() if line.strip()]
            if declared
            else sorted(_inferred_top_levels(dist.files or ()))
        )
        for name in names:
            mapping.setdefault(name, []).append(dist.metadata["Name"])
    return mapping


def bundled_python_packages(
    bundle: Path,
    runtime: Path,
    locked: list[tuple[str, str]],
    project_name: str,
) -> list[tuple[str, str]]:
    module_map = _module_to_distributions()
    mapped = {
        canonicalize_name(package)
        for module in _archive_top_level_modules(runtime, bundle)
        for package in module_map.get(module, ())
    }
    mapped.discard(canonicalize_name(project_name))
    locked_map = {canonicalize_name(name): version for name, version in locked}
    unpinned = sorted(mapped - set(locked_map))
    if unpinned:
        raise SystemExit(
            "bundled Python distributions are missing from requirements-runtime.lock: "
            f"{unpinned}"
        )
    return [
        (name, version)
        for name, version in locked
        if canonicalize_name(name) in mapped
    ]


def _native_version(paths: list[Path], pattern: bytes, component_name: str) -> str:
    versions = {
        match.decode("ascii")
        for path in paths
        for match in re.findall(pattern, path.read_bytes())
    }
    if len(versions) != 1:
        raise SystemExit(
            f"could not determine one {component_name} version from bundled files: "
            f"{sorted(versions)}"
        )
    return versions.pop()


def native_components(bundle: Path, project_root: Path) -> list[BundledComponent]:
    # Shared libpython dylibs (python-build-standalone / uv-managed
    # interpreters) belong to the Python runtime component, whose license
    # they share, not to the third-party native-library gate.
    dylibs = sorted(
        path
        for path in bundle.rglob("*.dylib")
        if not path.name.startswith("libpython")
    )
    unmatched = set(dylibs)
    components: list[BundledComponent] = []
    for definition in NATIVE_DEFINITIONS:
        matched = [
            path
            for path in dylibs
            if any(fnmatch.fnmatch(path.name, pattern) for pattern in definition.file_patterns)
        ]
        if not matched:
            continue
        unmatched.difference_update(matched)
        notice_texts: list[tuple[str, str]] = []
        for relative in definition.license_paths:
            license_path = project_root / relative
            if not license_path.is_file():
                raise SystemExit(
                    f"native component license material is missing: {license_path}"
                )
            notice_texts.append((license_path.name, safe_text(license_path)))
        components.append(
            BundledComponent(
                name=definition.name,
                version=_native_version(
                    matched, definition.version_pattern, definition.name
                ),
                license_declared=definition.license_declared,
                download_location=definition.download_location,
                notice_texts=tuple(notice_texts),
                bundled_files=tuple(str(path.relative_to(bundle)) for path in matched),
            )
        )
    if unmatched:
        raise SystemExit(
            "bundled native libraries have no owned license mapping: "
            f"{[str(path.relative_to(bundle)) for path in sorted(unmatched)]}"
        )
    return components


def python_component(bundle: Path) -> BundledComponent:
    framework_files = tuple(
        str(path.relative_to(bundle))
        for path in sorted(
            [
                *bundle.rglob("Python"),
                *bundle.rglob("libpython*.dylib"),
            ]
        )
        if path.is_file()
    )
    license_path = python_license()
    return BundledComponent(
        name="Python",
        version=".".join(str(part) for part in sys.version_info[:3]),
        license_declared="PSF-2.0",
        download_location="https://www.python.org/",
        notice_texts=((license_path.name, safe_text(license_path)),),
        bundled_files=framework_files or ("Python standard library runtime",),
    )


def distribution_component(
    requested_name: str,
    locked_version: str,
) -> BundledComponent:
    installed, paths = license_files(requested_name)
    installed_name = installed.metadata.get("Name", requested_name)
    if installed.version != locked_version:
        raise SystemExit(
            f"runtime lock drift for {installed_name}: expected {locked_version}, "
            f"installed {installed.version}"
        )
    return BundledComponent(
        name=installed_name,
        version=installed.version,
        license_declared=declared_license(installed),
        download_location="NOASSERTION",
        notice_texts=tuple((path.name, safe_text(path)) for path in paths),
        bundled_files=(f"frozen Python distribution: {installed_name}",),
    )


def pyinstaller_component(runtime: Path) -> BundledComponent:
    installed, paths = license_files("PyInstaller")
    return BundledComponent(
        name="PyInstaller bootloader",
        version=installed.version,
        license_declared="GPL-2.0-or-later WITH Bootloader-exception",
        download_location="https://pyinstaller.org/",
        notice_texts=tuple((path.name, safe_text(path)) for path in paths),
        bundled_files=(runtime.name,),
    )


def component_package(component: BundledComponent) -> dict[str, Any]:
    return {
        "SPDXID": spdx_id(component.name),
        "name": component.name,
        "versionInfo": component.version,
        "downloadLocation": component.download_location,
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": component.license_declared,
        "copyrightText": "NOASSERTION",
        "comment": "Bundled files: " + ", ".join(component.bundled_files),
    }


def build_components(
    project_path: Path,
    bundle: Path,
    runtime: Path,
    locked: list[tuple[str, str]],
) -> tuple[str, str, list[BundledComponent]]:
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
    project_name = project["name"]
    project_version = project["version"]
    bundled = bundled_python_packages(bundle, runtime, locked, project_name)
    components = [python_component(bundle)]
    components.extend(
        distribution_component(name, version) for name, version in bundled
    )
    components.append(pyinstaller_component(runtime))
    components.extend(native_components(bundle, project_path.parent))
    unresolved = sorted(
        f"{component.name}=={component.version}"
        for component in components
        if component.license_declared == "NOASSERTION"
    )
    if unresolved:
        raise SystemExit(
            "bundled components require an explicit reviewed SPDX license: "
            f"{unresolved}"
        )
    return project_name, project_version, components


def build_notice(components: list[BundledComponent]) -> str:
    sections = [
        "Math Anchor third-party notices",
        "Generated from the final bundled artifact and its exact dependency lock.",
    ]
    for component in components:
        texts = "".join(
            f"\n--- {label} ---\n{text}" for label, text in component.notice_texts
        )
        sections.append(
            f"\n{'=' * 78}\n{component.name} {component.version}\n"
            f"Declared license: {component.license_declared}\n"
            f"Bundled files: {', '.join(component.bundled_files)}\n"
            f"{'=' * 78}{texts}"
        )
    return "\n".join(sections) + "\n"


def artifact_digest(lock: Path, runtime: Path, components: list[BundledComponent]) -> str:
    digest = hashlib.sha256(lock.read_bytes())
    digest.update(hashlib.sha256(runtime.read_bytes()).digest())
    for component in components:
        digest.update(component.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(component.version.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def build_sbom(
    project_name: str,
    project_version: str,
    lock: Path,
    runtime: Path,
    components: list[BundledComponent],
) -> dict[str, Any]:
    root_id = spdx_id(project_name)
    root_package = {
        "SPDXID": root_id,
        "name": project_name,
        "versionInfo": project_version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "Apache-2.0",
        "copyrightText": "NOASSERTION",
        "primaryPackagePurpose": "APPLICATION",
    }
    packages = [root_package, *(component_package(item) for item in components)]
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        }
    ]
    relationships.extend(
        {
            "spdxElementId": root_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": spdx_id(component.name),
        }
        for component in components
    )
    namespace_hash = artifact_digest(lock, runtime, components)
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Math Anchor bundled runtime",
        "documentNamespace": f"https://spdx.org/spdxdocs/math-anchor-{namespace_hash}",
        "creationInfo": {
            "created": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "creators": ["Tool: MathAnchor-generate-third-party-materials"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def verify_existing_materials(
    output_dir: Path,
    project_name: str,
    project_version: str,
    components: list[BundledComponent],
) -> None:
    notice_path = output_dir / "THIRD_PARTY_NOTICES.txt"
    sbom_path = output_dir / "sbom.spdx.json"
    try:
        notice = notice_path.read_text(encoding="utf-8")
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"third-party release material is missing or invalid: {error}") from error

    expected_packages = {
        spdx_id(project_name): {
            "name": project_name,
            "versionInfo": project_version,
            "licenseDeclared": "Apache-2.0",
            "filesAnalyzed": False,
        }
    }
    expected_packages.update(
        {
            spdx_id(component.name): {
                key: value
                for key, value in component_package(component).items()
                if key in {
                    "name",
                    "versionInfo",
                    "licenseDeclared",
                    "filesAnalyzed",
                    "comment",
                }
            }
            for component in components
        }
    )
    actual_packages = {
        package.get("SPDXID"): package for package in sbom.get("packages", [])
    }
    if set(actual_packages) != set(expected_packages):
        raise SystemExit(
            "SBOM package inventory does not match the final artifact; "
            f"expected={sorted(expected_packages)}, actual={sorted(actual_packages)}"
        )
    for package_id, expected in expected_packages.items():
        actual = actual_packages[package_id]
        for key, value in expected.items():
            if actual.get(key) != value:
                raise SystemExit(
                    f"SBOM mismatch for {package_id}.{key}: "
                    f"expected {value!r}, found {actual.get(key)!r}"
                )
    for component in components:
        header = f"{component.name} {component.version}"
        if header not in notice:
            raise SystemExit(f"third-party notice is missing component: {header}")
        for bundled_file in component.bundled_files:
            if bundled_file not in notice:
                raise SystemExit(
                    f"third-party notice is missing bundled file: {bundled_file}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    arguments = parser.parse_args()

    if arguments.validate_only and arguments.verify_existing:
        raise SystemExit("--validate-only and --verify-existing are mutually exclusive")
    locked = locked_packages(arguments.lock)
    validate_dependency_closure(
        arguments.project,
        locked,
        project_extras=arguments.extra,
    )
    if arguments.validate_only:
        return
    if arguments.bundle is None or arguments.runtime is None or arguments.output_dir is None:
        raise SystemExit(
            "--bundle, --runtime, and --output-dir are required when generating or verifying materials"
        )

    bundle = arguments.bundle.resolve()
    runtime = arguments.runtime.resolve()
    output_dir = arguments.output_dir.resolve()
    if not runtime.is_file() or bundle not in runtime.parents:
        raise SystemExit("runtime must be an existing file inside the final bundle")
    project_name, project_version, components = build_components(
        arguments.project.resolve(), bundle, runtime, locked
    )
    if arguments.verify_existing:
        verify_existing_materials(
            output_dir, project_name, project_version, components
        )
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "THIRD_PARTY_NOTICES.txt").write_text(
        build_notice(components), encoding="utf-8"
    )
    sbom = build_sbom(
        project_name,
        project_version,
        arguments.lock,
        runtime,
        components,
    )
    (output_dir / "sbom.spdx.json").write_text(
        json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
