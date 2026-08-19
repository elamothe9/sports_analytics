#!/usr/bin/env python3
"""Internal setup helpers for worker shell scripts."""

from __future__ import annotations

import argparse
import re
import site
import sys
from pathlib import Path
from typing import Optional, Tuple


MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 14)


def is_supported_python(version_info: Tuple[int, int]) -> bool:
    return MIN_PYTHON <= version_info[:2] < MAX_PYTHON_EXCLUSIVE


def python_version_label(version_info: Tuple[int, int]) -> str:
    return f"Python {version_info[0]}.{version_info[1]}"


def python_version_error(
    version_info: Optional[Tuple[int, int]] = None,
    executable_label: Optional[str] = None,
) -> str:
    if version_info is None:
        version_info = sys.version_info[:2]
    executable = executable_label or sys.executable
    current = python_version_label(version_info)
    return (
        f"Error: {executable} is running {current}; setup requires Python 3.11, "
        "3.12, or 3.13. Install a supported Python version and rerun setup.sh."
    )


def check_python_version(_args: argparse.Namespace) -> int:
    if is_supported_python(sys.version_info[:2]):
        return 0
    if not _args.quiet:
        print(python_version_error(executable_label=_args.executable_label), file=sys.stderr)
    return 1


def python_executable(_args: argparse.Namespace) -> int:
    print(sys.executable)
    return 0


def site_packages(_args: argparse.Namespace) -> int:
    print(site.getsitepackages()[0])
    return 0


def patch_docker_cleanup(args: argparse.Namespace) -> int:
    content = args.file.read_text()
    patched, count = re.subn(
        r"(    def cleanup\(self\):)\n.*?(?=\n    def |\nclass |\Z)",
        r"\1  # PATCHED: cleanup disabled\n        pass\n",
        content,
        flags=re.DOTALL,
    )
    if count == 0:
        raise ValueError(f"Could not find cleanup method body in {args.file}")
    args.file.write_text(patched)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal setup helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check-python-version")
    check_parser.add_argument("--quiet", action="store_true")
    check_parser.add_argument("--executable-label")
    check_parser.set_defaults(func=check_python_version)

    executable_parser = subparsers.add_parser("python-executable")
    executable_parser.set_defaults(func=python_executable)

    site_packages_parser = subparsers.add_parser("site-packages")
    site_packages_parser.set_defaults(func=site_packages)

    patch_parser = subparsers.add_parser("patch-docker-cleanup")
    patch_parser.add_argument("--file", type=Path, required=True)
    patch_parser.set_defaults(func=patch_docker_cleanup)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
