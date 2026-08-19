#!/bin/bash
#
# Check Submission - optional pre-submission backstop for task authors.
#
# Reuses the existing task Docker image by default, then runs the pre-edit,
# task-attempt, and golden verification states followed by delivery packaging.
#
# Usage: ./check_submission.sh <task_dir> [--rebuild]
#
#   <task_dir>  - Path to task directory
#   --rebuild   - Rebuild and validate the Docker image before running checks
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="${1:-}"
REBUILD=false

usage() {
    echo ""
    echo "Usage: ./check_submission.sh <task_dir> [--rebuild]"
    echo ""
    echo "  <task_dir>  - Task directory"
    echo "  --rebuild   - Rebuild and validate the Docker image before running checks"
    echo ""
}

if [ -z "$TASK_DIR" ]; then
    usage
    exit 1
fi

shift || true
while [ "$#" -gt 0 ]; do
    case "$1" in
        --rebuild)
            REBUILD=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'."
            usage
            exit 1
            ;;
    esac
    shift
done

if ! TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"; then
    echo "Error: Task directory not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"

run_step() {
    local label="$1"
    shift

    echo ""
    echo "============================================"
    echo "  $label"
    echo "============================================"
    "$@"
}

echo ""
echo "============================================"
echo "  Check Submission"
echo "============================================"
echo ""
echo "Task:  $TASK_NAME"
echo "Image: $IMAGE_NAME"
echo ""

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running."
    exit 1
fi

if [ "$REBUILD" = true ]; then
    run_step "Validate Docker (--rebuild)" "$SCRIPT_DIR/validate_docker.sh" "$TASK_DIR"
elif docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Using existing Docker image. Pass --rebuild to rebuild and revalidate it."
else
    echo "Docker image not found. Running validate_docker.sh to build it."
    run_step "Validate Docker" "$SCRIPT_DIR/validate_docker.sh" "$TASK_DIR"
fi

run_step "Verify Pre-Edit State" \
    "$SCRIPT_DIR/verify_task_state.sh" "$TASK_DIR" pre-edit

run_step "Verify Task Attempt" \
    "$SCRIPT_DIR/verify_task_state.sh" "$TASK_DIR" task-attempt patches/test_agent_patch.diff

run_step "Verify Golden Solution" \
    "$SCRIPT_DIR/verify_task_state.sh" "$TASK_DIR" golden patches/golden_patch.diff

run_step "Generate Deliverables" \
    "$SCRIPT_DIR/create_delivery.sh" "$TASK_DIR"

echo ""
echo "============================================"
echo "  Submission Checks Passed"
echo "============================================"
echo ""
echo "All required checks completed successfully."
echo ""
