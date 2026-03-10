"""
utils.py
=============================
NovaWireless-GoodhartLab — Shared Utilities

Single source of truth for helpers used across all scripts.
Import with:
    from utils import find_repo_root
"""

from pathlib import Path


def find_repo_root(start=None) -> Path:
    """
    Walk up the directory tree to locate the repository root.

    Resolution order:
    1. Lowest ancestor directory that contains a ``.labroot`` marker file.
    2. Lowest ancestor directory that contains both ``src/`` and ``data/`` subdirs.
    3. Falls back to ``Path.cwd()`` if neither marker is found.
    """
    cur = Path(start or __file__).resolve()
    if cur.is_file():
        cur = cur.parent

    labroot_paths = []
    node = cur
    while True:
        if (node / ".labroot").exists():
            labroot_paths.append(node)
        if node.parent == node:
            break
        node = node.parent
    if labroot_paths:
        return labroot_paths[-1]

    node = cur
    while True:
        if (node / "src").is_dir() and (node / "data").is_dir():
            return node
        if node.parent == node:
            break
        node = node.parent

    return Path.cwd().resolve()
