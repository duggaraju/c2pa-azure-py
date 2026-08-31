#!/usr/bin/env python3
"""Keep the c2pa-azure version aligned with the pinned c2pa-python version."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("C2PA_SYNC_ROOT", Path(__file__).resolve().parents[1]))
REQUIREMENTS = ROOT / "requirements.txt"
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src/c2pa_azure/__init__.py"

VERSION_PATTERN = r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)?"


def pinned_c2pa_version(text: str) -> str:
    match = re.search(
        rf"^\s*c2pa-python\s*==\s*({VERSION_PATTERN})(?:\s*;.*)?\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        raise SystemExit("requirements.txt must pin c2pa-python with ==")
    return match.group(1)


def replace_once(text: str, pattern: str, replacement: str, filename: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not find exactly one version declaration in {filename}")
    return updated


def synced_contents(version: str) -> dict[Path, str]:
    pyproject = PYPROJECT.read_text()
    project_match = re.search(r"(?ms)^\[project\]\n(?P<body>.*?)(?=^\[|\Z)", pyproject)
    if not project_match:
        raise SystemExit("Could not find [project] in pyproject.toml")

    project_body = project_match.group("body")
    project_body = replace_once(
        project_body,
        rf'^version\s*=\s*"{VERSION_PATTERN}"$',
        f'version = "{version}"',
        "pyproject.toml",
    )

    major, minor, _ = version.split(".", 2)
    upper_bound = f"{major}.{int(minor) + 1}"
    project_body = replace_once(
        project_body,
        r'^\s*"c2pa-python[^\"]*",$',
        f'    "c2pa-python>={version},<{upper_bound}",',
        "pyproject.toml",
    )
    pyproject = (
        pyproject[: project_match.start("body")]
        + project_body
        + pyproject[project_match.end("body") :]
    )

    init = replace_once(
        INIT.read_text(),
        rf'^__version__\s*=\s*"{VERSION_PATTERN}"$',
        f'__version__ = "{version}"',
        "src/c2pa_azure/__init__.py",
    )
    return {PYPROJECT: pyproject, INIT: init}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of modifying files when versions are out of sync",
    )
    args = parser.parse_args()

    version = pinned_c2pa_version(REQUIREMENTS.read_text())
    expected = synced_contents(version)
    changed = [path for path, content in expected.items() if path.read_text() != content]

    if args.check and changed:
        relative = ", ".join(str(path.relative_to(ROOT)) for path in changed)
        raise SystemExit(f"Package version must match c2pa-python {version}: update {relative}")

    for path in changed:
        path.write_text(expected[path])

    action = "verified" if args.check else "synchronized"
    print(f"{action} c2pa-azure and c2pa-python at {version}")


if __name__ == "__main__":
    main()
