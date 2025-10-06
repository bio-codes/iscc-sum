"""
Platform-agnostic deterministic incremental directory tree traversal.

This module provides a layered approach to directory traversal:
1. `listdir`: Deterministic entry sorting using NFC-normalized UTF-8 encoding
2. `treewalk`: Basic traversal with ignore-file prioritization for early filtering
3. `treewalk_ignore`: Adds gitignore-style pattern matching with cascading rules
4. `treewalk_iscc`: ISCC-specific layer filtering metadata files

Each layer builds on the previous, ensuring consistent cross-platform ordering
while enabling progressive filtering capabilities for content hashing workflows.
"""

from __future__ import annotations

import os
from os import DirEntry
from pathlib import Path
from typing import Iterator
from unicodedata import normalize

import pathspec


def listdir(path):
    # type: (str|Path) -> list[DirEntry]
    """
    List directory entries with deterministic cross-platform sorting.

    Returns directory entries sorted by NFC-normalized UTF-8 encoded names,
    ensuring consistent ordering across different filesystems and locales.
    Symlinks are excluded for security and consistency.

    :param path: Directory path to list
    :return: Sorted list of DirEntry objects (excluding symlinks)
    """
    with os.scandir(path) as it:
        filtered = [e for e in it if not e.is_symlink()]
    return sorted(filtered, key=lambda e: (normalize("NFC", e.name).encode("utf-8"), e.name.encode("utf-8")))


def treewalk(path):
    # type: (str|Path) -> Iterator[Path]
    """
    Walk a directory tree and yield file paths in deterministic order.

    Yields paths in the following order:
    1. Ignore files (.*ignore) in current directory
    2. Regular files in current directory
    3. Files from subdirectories (recursively)

    The ordering is deterministic across platforms using NFC-normalized UTF-8 sorting.
    Symlinks are ignored for security and consistency.

    :param path: Directory path to walk
    :return: Iterator yielding Path objects for each file found
    """
    path = Path(path).resolve(strict=True)
    entries = listdir(path)
    dirs = [d for d in entries if d.is_dir()]
    files = [f for f in entries if f.is_file()]

    # First yield ignore files
    for file_entry in files:
        if file_entry.name.startswith(".") and file_entry.name.endswith("ignore"):
            yield Path(file_entry.path)

    # Then yield non-ignore files
    for file_entry in files:
        if not (file_entry.name.startswith(".") and file_entry.name.endswith("ignore")):
            yield Path(file_entry.path)

    # Then recurse into directories
    for dir_entry in dirs:
        yield from treewalk(Path(dir_entry.path))


def treewalk_ignore(path, ignore_file_name, root_path=None, ignore_spec=None):
    # type: (str|Path, str, Path|None, pathspec.PathSpec|None) -> Iterator[Path]
    """
    Walk a directory tree while respecting ignore file patterns.

    Yields paths in deterministic order while filtering based on accumulated
    ignore patterns from the root down to each subdirectory.

    :param path: Directory to walk
    :param ignore_file_name: Name of the ignore-file to look for (e.g., '.gitignore')
    :param root_path: Root directory for relative path calculations (defaults to the path argument)
    :param ignore_spec: Existing PathSpec with ignored patterns to extend
    :return: Iterator yielding Path objects for non-ignored files
    """
    path = Path(path).resolve(strict=True)
    if root_path is None:
        root_path = path
    else:
        root_path = Path(root_path).resolve(strict=True)

    # Load local ignore rules if present
    local_ignore = path / ignore_file_name
    if local_ignore.exists():
        with open(local_ignore, "r", encoding="utf-8") as f:
            new_spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, f)
            ignore_spec = new_spec if ignore_spec is None else ignore_spec + new_spec

    entries = listdir(path)
    dirs = [d for d in entries if d.is_dir()]
    files = [f for f in entries if f.is_file()]

    def should_ignore(fp, is_dir=False):
        if ignore_spec is None:
            return False
        rel_path = fp.relative_to(root_path)

        if is_dir:
            # For directories, check with trailing slash first (more specific)
            # If the directory with trailing slash is not ignored, don't ignore it
            # This allows patterns like "!subdir/" to override "*"
            dir_with_slash = str(rel_path) + "/"
            if not ignore_spec.match_file(dir_with_slash):
                return False
            # If dir with slash would be ignored, also check without slash
            return ignore_spec.match_file(rel_path)
        else:
            # For files, only check the file pattern
            return ignore_spec.match_file(rel_path)

    # First yield ignore files including the current one
    for file_entry in files:
        file_path = Path(file_entry.path)
        if file_entry.name.startswith(".") and file_entry.name.endswith("ignore"):
            if not should_ignore(file_path, is_dir=False):
                yield file_path

    # Then yield non-ignore files
    for file_entry in files:
        file_path = Path(file_entry.path)
        if not (file_entry.name.startswith(".") and file_entry.name.endswith("ignore")):
            if not should_ignore(file_path, is_dir=False):
                yield file_path

    # Then recurse into directories
    for dir_entry in dirs:
        dir_path = Path(dir_entry.path)
        if not should_ignore(dir_path, is_dir=True):
            yield from treewalk_ignore(dir_path, ignore_file_name, root_path, ignore_spec)


def treewalk_iscc(path):
    # type: (str|Path) -> Iterator[Path]
    """
    Walk directory tree with ISCC-specific ignore rules.

    Automatically filters out:
    - Files ending with '.iscc.json' (ISCC metadata files)
    - Paths matching patterns in '.isccignore' files

    Uses the same deterministic ordering as treewalk_ignore.

    :param path: Directory path to walk
    :return: Iterator yielding Path objects for non-ignored, non-ISCC metadata files
    """
    path = Path(path).resolve(strict=True)

    # Use treewalk_ignore with .isccignore files
    for file_path in treewalk_ignore(path, ".isccignore"):
        # Skip files ending with .iscc.json
        if not file_path.name.endswith(".iscc.json"):
            yield file_path


if __name__ == "__main__":  # pragma: no cover
    import pathlib
    import sys

    HERE = pathlib.Path(__file__).parent.absolute()
    ROOT = HERE.parent.parent.absolute()
    for entry in treewalk_iscc(ROOT):
        print(entry.as_posix())
