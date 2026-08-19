#!/bin/bash
#
# Extract Patch — Reconstruct a diff from a trajectory file
#
# Replays all commands from a mini-swe-agent trajectory in a fresh
# Docker container and extracts the resulting git diff.
#
# Use this when run_task.sh fails to extract the diff automatically.
#
# Usage: ./extract_patch.sh <task_dir> <trajectory_file> [output_file]
#
#   <task_dir>         - Path to task directory (must have a built Docker image)
#   <trajectory_file>  - Path to trajectory JSON file
#   [output_file]      - Output patch file (default: patches/<model>_patch.diff)
#
# Examples:
#   ./extract_patch.sh ./my-task trajectories/test_agent_trajectory.json
#   ./extract_patch.sh ./my-task trajectories/golden_trajectory.json patches/golden_patch.diff
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/patch_utils.sh
source "$SCRIPT_DIR/internal/patch_utils.sh"
# shellcheck source=internal/docker_run_args.sh
source "$SCRIPT_DIR/internal/docker_run_args.sh"

TASK_DIR="${1:-}"
TRAJ_FILE="${2:-}"
OUTPUT_FILE="${3:-}"

if [ -z "$TASK_DIR" ] || [ -z "$TRAJ_FILE" ]; then
    echo ""
    echo "Usage: ./extract_patch.sh <task_dir> <trajectory_file> [output_file]"
    echo ""
    echo "Examples:"
    echo "  ./extract_patch.sh ./my-task trajectories/test_agent_trajectory.json"
    echo "  ./extract_patch.sh ./my-task trajectories/golden_trajectory.json patches/golden_patch.diff"
    echo ""
    exit 1
fi

# Resolve paths
TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"
if [ -z "$TASK_DIR" ]; then
    echo "Error: Task directory not found."
    exit 1
fi

# Resolve trajectory path (relative to task dir if not absolute)
if [[ "$TRAJ_FILE" != /* ]]; then
    TRAJ_FILE="$TASK_DIR/$TRAJ_FILE"
fi

if [ ! -f "$TRAJ_FILE" ]; then
    echo "Error: Trajectory file not found: $TRAJ_FILE"
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"

# Default output file
if [ -z "$OUTPUT_FILE" ]; then
    TRAJ_BASENAME="$(basename "$TRAJ_FILE" .json)"
    MODEL_NAME="${TRAJ_BASENAME%_trajectory}"
    OUTPUT_FILE="$TASK_DIR/patches/${MODEL_NAME}_patch.diff"
fi
if [[ "$OUTPUT_FILE" != /* ]]; then
    OUTPUT_FILE="$TASK_DIR/$OUTPUT_FILE"
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

echo ""
echo "============================================"
echo "  Extract Patch from Trajectory"
echo "============================================"
echo ""
echo "Task:        $TASK_NAME"
echo "Trajectory:  $TRAJ_FILE"
echo "Output:      $OUTPUT_FILE"
echo ""

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running."
    exit 1
fi

if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Error: Docker image '$IMAGE_NAME' not found."
    echo "Run validate_docker.sh first."
    exit 1
fi

# ─────────────────────────────────────────────
# Extract commands from trajectory
# ─────────────────────────────────────────────
echo "--- Extracting commands from trajectory ---"

VENV_DIR="$HOME/mini-sweagent-env"
if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
fi

REPLAY_SCRIPT="$(mktemp)"

python3 "$SCRIPT_DIR/internal/task_artifacts.py" write-replay-script \
    --trajectory "$TRAJ_FILE" \
    --output "$REPLAY_SCRIPT"

if [ ! -s "$REPLAY_SCRIPT" ]; then
    echo "Error: No commands extracted from trajectory."
    rm -f "$REPLAY_SCRIPT"
    exit 1
fi

CMD_COUNT=$(wc -l < "$REPLAY_SCRIPT" | tr -d ' ')
echo "Replay script: $CMD_COUNT lines"

# ─────────────────────────────────────────────
# Replay in fresh container
# ─────────────────────────────────────────────
echo ""
echo "--- Replaying in fresh container ---"
echo "(this may take a minute...)"

load_etalon_docker_run_args
print_etalon_docker_run_args
CONTAINER=$(docker_run_detached "$IMAGE_NAME" sleep 600)
echo "Container: $CONTAINER"

docker cp "$REPLAY_SCRIPT" "$CONTAINER:/tmp/replay.sh"
rm -f "$REPLAY_SCRIPT"

set +e
docker exec "$CONTAINER" bash /tmp/replay.sh > /dev/null 2>&1
set -e

# ─────────────────────────────────────────────
# Extract diff
# ─────────────────────────────────────────────
echo ""
echo "--- Extracting diff ---"

extract_container_patch "$CONTAINER" "$OUTPUT_FILE"

# ─────────────────────────────────────────────
# Interactive fallback: let worker inspect
# ─────────────────────────────────────────────
if [ ! -s "$OUTPUT_FILE" ]; then
    echo ""
    echo "  Automatic diff extraction found no changes."
    echo ""
    echo "  The container is still running. You can inspect it manually:"
    echo "    docker exec -it $CONTAINER bash"
    echo ""
    echo "  Check what changed:"
    echo "    git diff"
    echo "    git status"
    echo "    git log --oneline"
    echo ""
    echo "  When done, extract the diff yourself:"
    echo "    docker exec $CONTAINER git -C /app diff > $OUTPUT_FILE"
    echo ""
    echo "  Then clean up:"
    echo "    docker stop $CONTAINER && docker rm $CONTAINER"
    echo ""
    exit 1
fi

# ─────────────────────────────────────────────
# Cleanup and report
# ─────────────────────────────────────────────
docker stop "$CONTAINER" > /dev/null 2>&1
docker rm "$CONTAINER" > /dev/null 2>&1

LINES=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')
echo ""
echo "============================================"
echo "  Patch extracted: $LINES lines"
echo "============================================"
echo ""
echo "Output: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "  ./verify_task_state.sh $(basename "$TASK_DIR") task-attempt $(echo "$OUTPUT_FILE" | sed "s|$TASK_DIR/||")"
echo "  # Use state 'golden' instead if this is your golden patch."
echo ""
