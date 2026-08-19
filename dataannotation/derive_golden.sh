#!/bin/bash
#
# Derive Golden Solution — Tool-agnostic golden patch creation
#
# Starts a Docker container with the clean base-commit codebase and waits
# for you to make changes using any tool (Claude Code, Codex, manual edits,
# shell into the container, etc.). When you're done, it extracts the diff.
#
# Usage: ./derive_golden.sh <task_dir>
#
# Examples:
#   ./derive_golden.sh ./my-task
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/patch_utils.sh
source "$SCRIPT_DIR/internal/patch_utils.sh"
# shellcheck source=internal/docker_run_args.sh
source "$SCRIPT_DIR/internal/docker_run_args.sh"

TASK_DIR="${1:-}"

if [ -z "$TASK_DIR" ]; then
    echo ""
    echo "Usage: ./derive_golden.sh <task_dir>"
    echo ""
    exit 1
fi

TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"
if [ -z "$TASK_DIR" ]; then
    echo "Error: Task directory not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"
PATCHES_DIR="$TASK_DIR/patches"
PATCH_FILE="$PATCHES_DIR/golden_patch.diff"

mkdir -p "$PATCHES_DIR"

echo ""
echo "============================================"
echo "  Derive Golden Solution"
echo "============================================"
echo ""
echo "Task: $TASK_NAME"
echo ""

# Check prerequisites
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
# Start container
# ─────────────────────────────────────────────
echo "--- Starting container ---"

load_etalon_docker_run_args
print_etalon_docker_run_args
CONTAINER=$(docker_run_detached -v "$TASK_DIR:/host" "$IMAGE_NAME" sleep 3600)
echo "Container: $CONTAINER"
echo ""

# ─────────────────────────────────────────────
# Show instructions
# ─────────────────────────────────────────────
echo "Container is running with the clean base-commit codebase at /app."
echo "The task directory is mounted at /host (read-only reference)."
echo ""
echo "You can now derive the golden solution using any method:"
echo ""
echo "  Option A: Shell into the container"
echo "    docker exec -it $CONTAINER bash"
echo "    cd /app"
echo "    # ... make your changes ..."
echo ""
echo "  Option B: Copy files in from the host"
echo "    docker cp my_fix.py $CONTAINER:/app/src/my_fix.py"
echo ""
echo "  Option C: Run a command in the container"
echo "    docker exec $CONTAINER bash -c 'cd /app && sed -i ...'"
echo ""
echo "  Option D: Use Claude Code / Codex on the host, then copy changes in"
echo "    docker cp ./src/ $CONTAINER:/app/src/"
echo ""
echo "============================================"
echo ""

# ─────────────────────────────────────────────
# Wait for user
# ─────────────────────────────────────────────
read -rp "Press Enter when you're done making changes (or 'q' to abort)... " INPUT

if [[ "$INPUT" == "q" || "$INPUT" == "Q" ]]; then
    echo ""
    echo "Aborting. Cleaning up container..."
    docker stop "$CONTAINER" > /dev/null 2>&1
    docker rm "$CONTAINER" > /dev/null 2>&1
    exit 0
fi

# ─────────────────────────────────────────────
# Extract diff
# ─────────────────────────────────────────────
echo ""
echo "--- Extracting diff ---"

extract_container_patch "$CONTAINER" "$PATCH_FILE"

# ─────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────
if [ -s "$PATCH_FILE" ]; then
    LINES=$(wc -l < "$PATCH_FILE" | tr -d ' ')
    echo ""
    echo "============================================"
    echo "  Golden patch extracted: $LINES lines"
    echo "============================================"
    echo ""
    echo "Output: $PATCH_FILE"
    echo ""
    echo "Next: verify it passes golden tests:"
    echo "  ./verify_task_state.sh $(basename "$TASK_DIR") golden patches/golden_patch.diff"
    echo ""

    # Cleanup
    docker stop "$CONTAINER" > /dev/null 2>&1
    docker rm "$CONTAINER" > /dev/null 2>&1
else
    echo ""
    echo "WARNING: No changes detected."
    echo ""
    echo "The container is still running so you can investigate:"
    echo "  docker exec -it $CONTAINER bash"
    echo "  cd /app && git status && git diff"
    echo ""
    echo "Extract manually if needed:"
    echo "  docker exec $CONTAINER git -C /app diff > $PATCH_FILE"
    echo ""
    echo "Then clean up:"
    echo "  docker stop $CONTAINER && docker rm $CONTAINER"
fi
