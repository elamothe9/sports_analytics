#!/usr/bin/env python3
"""Internal helpers for run_task.sh.

This module is intentionally not a worker-facing command. The shell wrapper uses
it for YAML operations that are brittle in bash.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml


def parse_int(name: str, value: Any, *, min_value: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got: {value!r}")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        result = int(value.strip())
    else:
        raise ValueError(f"{name} must be an integer, got: {value!r}")
    if result < min_value:
        raise ValueError(f"{name} must be at least {min_value}, got: {result}")
    return result


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def parse_docker_run_args() -> list[str]:
    raw = os.environ.get("ETALON_DOCKER_RUN_ARGS", "")
    if not raw.strip():
        return []
    return raw.split()


def prepare(args: argparse.Namespace) -> int:
    cfg = load_config(args.config_file)
    worker_tools = cfg.get("worker_tools") or {}
    if not isinstance(worker_tools, dict):
        raise ValueError("worker_tools must be a YAML mapping")

    timeout = parse_int(
        "worker_tools.model_request_timeout_seconds",
        worker_tools.get("model_request_timeout_seconds", 600),
        min_value=1,
    )
    retries = parse_int(
        "worker_tools.model_request_retries",
        worker_tools.get("model_request_retries", 0),
        min_value=0,
    )

    model_cfg = cfg.setdefault("model", {})
    if not isinstance(model_cfg, dict):
        raise ValueError("model must be a YAML mapping")
    model_name = model_cfg["model_name"]
    model_kwargs = model_cfg.setdefault("model_kwargs", {})
    if not isinstance(model_kwargs, dict):
        raise ValueError("model.model_kwargs must be a YAML mapping")

    environment_cfg = cfg.setdefault("environment", {})
    if not isinstance(environment_cfg, dict):
        raise ValueError("environment must be a YAML mapping")
    environment_cfg["image"] = args.image_name
    docker_run_args = parse_docker_run_args()
    run_args = environment_cfg.get("run_args") or []
    if not isinstance(run_args, list) or not all(isinstance(item, str) for item in run_args):
        raise ValueError("environment.run_args must be a list of strings")
    environment_cfg["run_args"] = [*run_args, *docker_run_args]

    api_key = os.environ.get("MINI_SWE_CONFIG_API_KEY", "")
    if not api_key:
        raise ValueError("MINI_SWE_CONFIG_API_KEY is required")
    model_kwargs["api_key"] = api_key
    model_kwargs["timeout"] = timeout

    # worker_tools is consumed by run_task.sh and is not part of mini-swe-agent's config schema.
    cfg.pop("worker_tools", None)

    args.task_config.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(model_name)
    print(timeout)
    print(retries)
    print(retries + 1)
    return 0


def scrub(args: argparse.Namespace) -> int:
    api_key = os.environ.get("MINI_SWE_CONFIG_API_KEY", "")
    if not api_key:
        return 0

    for path in args.files:
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        if api_key in text:
            path.write_text(text.replace(api_key, "<MINI_SWE_API_KEY>"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal run_task.sh helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--config-file", type=Path, required=True)
    prepare_parser.add_argument("--task-config", type=Path, required=True)
    prepare_parser.add_argument("--image-name", required=True)
    prepare_parser.set_defaults(func=prepare)

    scrub_parser = subparsers.add_parser("scrub")
    scrub_parser.add_argument("files", type=Path, nargs="+")
    scrub_parser.set_defaults(func=scrub)

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
