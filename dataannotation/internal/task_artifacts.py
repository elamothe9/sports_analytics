#!/usr/bin/env python3
"""Internal task artifact helpers for worker shell scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_file(path: Path) -> str | None:
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


def render_dockerfile(args: argparse.Namespace) -> int:
    text = args.dockerfile.read_text()
    text = text.replace("__ETALON_REPO_URL__", args.repo_url)
    text = text.replace("__ETALON_BASE_COMMIT__", args.base_commit)
    args.dockerfile.write_text(text)
    return 0


def metadata_field(args: argparse.Namespace) -> int:
    metadata = load_json(args.metadata)
    value = metadata.get(args.field, "")
    if value is None:
        value = ""
    print(value)
    return 0


def extract_commands(trajectory: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for msg in trajectory.get("messages", []):
        if not isinstance(msg, dict):
            continue
        for tool_call in msg.get("tool_calls", []):
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function", {})
            if not isinstance(function, dict):
                continue
            tool_args = function.get("arguments", "")
            if isinstance(tool_args, str):
                try:
                    parsed = json.loads(tool_args)
                    cmd = parsed.get("command", "") if isinstance(parsed, dict) else tool_args
                except (json.JSONDecodeError, AttributeError):
                    cmd = tool_args
            elif isinstance(tool_args, dict):
                cmd = tool_args.get("command", "")
            else:
                continue

            if not cmd or "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in cmd:
                continue
            commands.append(cmd)
    return commands


def write_replay_script(args: argparse.Namespace) -> int:
    trajectory = load_json(args.trajectory)
    commands = extract_commands(trajectory)
    with args.output.open("w") as f:
        f.write("#!/bin/bash\nset +e\ncd /app\n")
        for cmd in commands:
            f.write(cmd + "\n")
        f.write("\n")
    print(f"Found {len(commands)} commands")
    return 0


def write_instance(args: argparse.Namespace) -> int:
    task_dir = args.task_dir
    patches_dir = args.patches_dir

    metadata = {}
    metadata_path = task_dir / ".task_metadata.json"
    if metadata_path.exists():
        metadata = load_json(metadata_path)

    repo = metadata.get("repo", "")
    base_commit = metadata.get("base_commit", "")
    instance_id = repo.replace("/", "__") + "-" + args.task_name if repo else args.task_name

    instance = {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": base_commit,
        "problem_statement": read_file(task_dir / "prompt.md"),
        "patch": read_file(patches_dir / "golden_patch.diff"),
        "test_patch": read_file(patches_dir / "test_patch.diff"),
        "test_cmds": [
            f"bash {args.f2p_entrypoint}",
            f"bash {args.p2p_entrypoint}",
        ],
        "FAIL_TO_PASS": json.dumps([args.f2p_entrypoint]),
        "PASS_TO_PASS": json.dumps([args.p2p_entrypoint]),
    }

    dockerfile_content = read_file(task_dir / "Dockerfile")
    if dockerfile_content:
        instance["DockerFile"] = dockerfile_content

    agent_patch = read_file(patches_dir / "test_agent_patch.diff")
    if agent_patch:
        instance["agent_patch"] = agent_patch

    (patches_dir / "instance.json").write_text(json.dumps(instance, indent=2))

    display = dict(instance)
    for key in ("patch", "test_patch", "agent_patch", "problem_statement"):
        if display.get(key) and len(display[key]) > 100:
            display[key] = display[key][:100] + "..."
    print(json.dumps(display, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal task artifact helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render-dockerfile")
    render_parser.add_argument("--dockerfile", type=Path, required=True)
    render_parser.add_argument("--repo-url", required=True)
    render_parser.add_argument("--base-commit", required=True)
    render_parser.set_defaults(func=render_dockerfile)

    metadata_parser = subparsers.add_parser("metadata-field")
    metadata_parser.add_argument("--metadata", type=Path, required=True)
    metadata_parser.add_argument("--field", required=True)
    metadata_parser.set_defaults(func=metadata_field)

    replay_parser = subparsers.add_parser("write-replay-script")
    replay_parser.add_argument("--trajectory", type=Path, required=True)
    replay_parser.add_argument("--output", type=Path, required=True)
    replay_parser.set_defaults(func=write_replay_script)

    instance_parser = subparsers.add_parser("write-instance")
    instance_parser.add_argument("--task-dir", type=Path, required=True)
    instance_parser.add_argument("--task-name", required=True)
    instance_parser.add_argument("--patches-dir", type=Path, required=True)
    instance_parser.add_argument("--f2p-entrypoint", required=True)
    instance_parser.add_argument("--p2p-entrypoint", required=True)
    instance_parser.set_defaults(func=write_instance)

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
