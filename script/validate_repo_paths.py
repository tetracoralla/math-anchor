#!/usr/bin/env python3
"""Reject repository output paths that can escape through symbolic links."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys


class UnsafeRepositoryPath(ValueError):
    """Raised when an output path is not a safe descendant of the repository."""


def _is_within(parent: str, child: str) -> bool:
    try:
        return os.path.commonpath((parent, child)) == parent
    except ValueError:
        return False


def validate_repository_path(root: Path, target: Path) -> None:
    root_path = os.path.abspath(os.fspath(root))
    target_path = os.path.abspath(os.fspath(target))

    try:
        root_status = os.lstat(root_path)
    except OSError as error:
        raise UnsafeRepositoryPath(
            f"repository root cannot be inspected: {root_path}: {error}"
        ) from error
    if stat.S_ISLNK(root_status.st_mode):
        raise UnsafeRepositoryPath(
            f"repository root must not be a symbolic link: {root_path}"
        )
    if not stat.S_ISDIR(root_status.st_mode):
        raise UnsafeRepositoryPath(f"repository root is not a directory: {root_path}")
    if not _is_within(root_path, target_path):
        raise UnsafeRepositoryPath(
            f"path is not lexically inside the repository: {target_path}"
        )

    relative = os.path.relpath(target_path, root_path)
    cursor = root_path
    for component in Path(relative).parts:
        cursor = os.path.join(cursor, component)
        try:
            component_status = os.lstat(cursor)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise UnsafeRepositoryPath(
                f"path component cannot be inspected: {cursor}: {error}"
            ) from error
        if stat.S_ISLNK(component_status.st_mode):
            raise UnsafeRepositoryPath(
                f"path contains a symbolic-link component: {cursor}"
            )

    resolved_root = os.path.realpath(root_path)
    resolved_target = os.path.realpath(target_path)
    if not _is_within(resolved_root, resolved_target):
        raise UnsafeRepositoryPath(
            "resolved path escapes the repository: "
            f"{target_path} -> {resolved_target}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that output paths remain inside a repository."
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("paths", nargs="+", type=Path)
    arguments = parser.parse_args()

    try:
        for target in arguments.paths:
            validate_repository_path(arguments.root, target)
    except UnsafeRepositoryPath as error:
        print(f"Unsafe repository path: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
