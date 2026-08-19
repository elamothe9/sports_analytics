#!/bin/bash
#
# Verify Task State - run hidden F2P/P2P entrypoints against a code state.
#
# Usage: ./verify_task_state.sh <task_dir> <state> [patch_file]
#
#   <task_dir>    - Path to task directory
#   <state>       - pre-edit | task-attempt | golden
#   [patch_file]  - Patch to apply for task-attempt or golden states
#
# Defaults:
#   task-attempt  -> patches/test_agent_patch.diff
#   golden        -> patches/golden_patch.diff
#
# Examples:
#   ./verify_task_state.sh ./my-task pre-edit
#   ./verify_task_state.sh ./my-task task-attempt patches/test_agent_patch.diff
#   ./verify_task_state.sh ./my-task golden patches/golden_patch.diff
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/docker_run_args.sh
source "$SCRIPT_DIR/internal/docker_run_args.sh"

TASK_DIR="${1:-}"
STATE="${2:-}"
PATCH_ARG="${3:-}"

F2P_SCRIPT="run_tests_f2p.sh"
P2P_SCRIPT="run_tests_p2p.sh"

usage() {
    echo ""
    echo "Usage: ./verify_task_state.sh <task_dir> <state> [patch_file]"
    echo ""
    echo "  <task_dir>    - Task directory"
    echo "  <state>       - pre-edit | task-attempt | golden"
    echo "  [patch_file]  - Patch to apply for task-attempt or golden states"
    echo ""
    echo "Examples:"
    echo "  ./verify_task_state.sh ./my-task pre-edit"
    echo "  ./verify_task_state.sh ./my-task task-attempt patches/test_agent_patch.diff"
    echo "  ./verify_task_state.sh ./my-task golden patches/golden_patch.diff"
    echo ""
}

has_required_entrypoints() {
    local tests_dir="$1"
    [ -f "$tests_dir/$F2P_SCRIPT" ] && [ -f "$tests_dir/$P2P_SCRIPT" ]
}

run_entrypoint() {
    local label="$1"
    local script="$2"
    local output_var="$3"
    local exit_var="$4"

    echo ""
    echo "--- Running $label: golden_tests/$script ---"
    set +e
    local output
    output=$(docker exec "$CONTAINER_ID" bash -c "cd /app && bash golden_tests/$script" 2>&1)
    local status=$?
    set -e
    echo "$output"
    printf -v "$output_var" '%s' "$output"
    printf -v "$exit_var" '%s' "$status"
}

failed_group_summary() {
    local summary=""

    if [ "$F2P_EXIT" -ne 0 ]; then
        summary="F2P"
    fi

    if [ "$P2P_EXIT" -ne 0 ]; then
        if [ -n "$summary" ]; then
            summary="$summary and P2P"
        else
            summary="P2P"
        fi
    fi

    echo "$summary"
}

if [ -z "$TASK_DIR" ] || [ -z "$STATE" ]; then
    usage
    exit 1
fi

case "$STATE" in
    pre-edit)
        EXPECTATION="F2P fails and P2P passes"
        ;;
    task-attempt)
        EXPECTATION="F2P or P2P fails"
        ;;
    golden)
        EXPECTATION="F2P and P2P both pass"
        ;;
    *)
        echo "Error: Unknown state '$STATE'."
        usage
        exit 1
        ;;
esac

if ! TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"; then
    echo "Error: Task directory not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"
PATCHES_DIR="$TASK_DIR/patches"
PATCH_FILE=""

if [ "$STATE" = "pre-edit" ]; then
    if [ -n "$PATCH_ARG" ]; then
        echo "Error: pre-edit state runs without a patch."
        exit 1
    fi
else
    if [ -n "$PATCH_ARG" ]; then
        if [[ "$PATCH_ARG" != /* ]]; then
            PATCH_FILE="$TASK_DIR/$PATCH_ARG"
        else
            PATCH_FILE="$PATCH_ARG"
        fi
    elif [ "$STATE" = "task-attempt" ]; then
        PATCH_FILE="$PATCHES_DIR/test_agent_patch.diff"
    else
        PATCH_FILE="$PATCHES_DIR/golden_patch.diff"
    fi
fi

GOLDEN_TESTS_DIR="$TASK_DIR/golden_tests"
if ! has_required_entrypoints "$GOLDEN_TESTS_DIR"; then
    GOLDEN_TESTS_DIR="$PATCHES_DIR/golden_tests_backup"
fi

echo ""
echo "============================================"
echo "  Verify Task State"
echo "============================================"
echo ""
echo "Task:         $TASK_NAME"
echo "State:        $STATE"
echo "Expected:     $EXPECTATION"
if [ -n "$PATCH_FILE" ]; then
    echo "Patch:        $PATCH_FILE"
else
    echo "Patch:        none"
fi
echo "Golden tests: $GOLDEN_TESTS_DIR"
echo ""

if [ -n "$PATCH_FILE" ]; then
    if [ ! -f "$PATCH_FILE" ]; then
        echo "Error: Patch file not found: $PATCH_FILE"
        exit 1
    fi

    if [ ! -s "$PATCH_FILE" ]; then
        echo "Error: Patch file is empty: $PATCH_FILE"
        exit 1
    fi
fi

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running."
    exit 1
fi

if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Error: Docker image '$IMAGE_NAME' not found."
    echo "Run validate_docker.sh first."
    exit 1
fi

if ! has_required_entrypoints "$GOLDEN_TESTS_DIR"; then
    echo "Error: Required golden test entrypoints not found."
    echo "Expected:"
    echo "  $GOLDEN_TESTS_DIR/$F2P_SCRIPT"
    echo "  $GOLDEN_TESTS_DIR/$P2P_SCRIPT"
    echo "Checked: $TASK_DIR/golden_tests/ and $PATCHES_DIR/golden_tests_backup/"
    exit 1
fi

CONTAINER_ID=""
cleanup_container() {
    if [ -n "$CONTAINER_ID" ]; then
        docker stop "$CONTAINER_ID" > /dev/null 2>&1 || true
        docker rm "$CONTAINER_ID" > /dev/null 2>&1 || true
    fi
}
trap cleanup_container EXIT

echo "--- Starting fresh container ---"
load_etalon_docker_run_args
print_etalon_docker_run_args
CONTAINER_ID=$(docker_run_detached "$IMAGE_NAME" sleep 1800)
echo "Container: $CONTAINER_ID"

if [ -n "$PATCH_FILE" ]; then
    echo ""
    echo "--- Applying patch ---"
    docker cp "$PATCH_FILE" "$CONTAINER_ID:/tmp/task-state.patch"
    set +e
    APPLY_OUTPUT=$(docker exec "$CONTAINER_ID" bash -c "cd /app && git apply /tmp/task-state.patch" 2>&1)
    APPLY_STATUS=$?
    set -e
    if [ "$APPLY_STATUS" -ne 0 ]; then
        echo "Error: Patch did not apply cleanly."
        echo "$APPLY_OUTPUT"
        exit 1
    fi
    echo "Patch applied."
else
    echo ""
    echo "--- Using clean pre-edit codebase ---"
fi

echo ""
echo "--- Adding golden tests ---"
docker exec "$CONTAINER_ID" rm -rf /app/golden_tests
docker cp "$GOLDEN_TESTS_DIR" "$CONTAINER_ID:/app/golden_tests"
TEST_FILE_COUNT=$(find "$GOLDEN_TESTS_DIR" -type f | wc -l | tr -d ' ')
echo "Copied $TEST_FILE_COUNT golden test file(s) into container."

F2P_OUTPUT=""
P2P_OUTPUT=""
F2P_EXIT=0
P2P_EXIT=0

run_entrypoint "F2P" "$F2P_SCRIPT" F2P_OUTPUT F2P_EXIT
run_entrypoint "P2P" "$P2P_SCRIPT" P2P_OUTPUT P2P_EXIT

echo ""
echo "============================================"

EXPECTATIONS_OK=false
case "$STATE" in
    pre-edit)
        if [ "$F2P_EXIT" -ne 0 ] && [ "$P2P_EXIT" -eq 0 ]; then
            EXPECTATIONS_OK=true
        fi
        ;;
    task-attempt)
        if [ "$F2P_EXIT" -ne 0 ] || [ "$P2P_EXIT" -ne 0 ]; then
            EXPECTATIONS_OK=true
        fi
        ;;
    golden)
        if [ "$F2P_EXIT" -eq 0 ] && [ "$P2P_EXIT" -eq 0 ]; then
            EXPECTATIONS_OK=true
        fi
        ;;
esac

case "$STATE" in
    task-attempt)
        if [ "$EXPECTATIONS_OK" = true ]; then
            FAILED_GROUPS="$(failed_group_summary)"
            echo "  Difficulty check: the test agent failed $FAILED_GROUPS, meaning the task is difficult enough."
            echo ""
            echo "  Go ahead to the next stage."
            EXIT_CODE=0
        else
            echo "  Difficulty check: the test agent passed both F2P and P2P."
            echo ""
            echo "  The task is too easy for this test-agent attempt. Make the task harder, or try a different task, then rerun this check."
            EXIT_CODE=1
        fi
        ;;
    pre-edit)
        if [ "$EXPECTATIONS_OK" = true ]; then
            echo "  RESULT: PASS"
            echo "  Pre-edit expectations satisfied: F2P failed and P2P passed."
            EXIT_CODE=0
        else
            echo "  RESULT: FAIL"
            echo "  Expected the pre-edit codebase to fail F2P and pass P2P."
            if [ "$F2P_EXIT" -eq 0 ]; then
                echo "  F2P passed before any edits, so it may not capture the requested change."
            fi
            if [ "$P2P_EXIT" -ne 0 ]; then
                echo "  P2P failed before any edits, so it may not be a stable regression check."
            fi
            EXIT_CODE=1
        fi
        ;;
    golden)
        if [ "$EXPECTATIONS_OK" = true ]; then
            echo "  RESULT: PASS"
            echo "  Golden expectations satisfied: F2P and P2P both passed."
            EXIT_CODE=0
        else
            echo "  RESULT: FAIL"
            echo "  Expected the golden patch to pass F2P and P2P."
            EXIT_CODE=1
        fi
        ;;
esac

echo ""
echo "  F2P exit code: $F2P_EXIT"
echo "  P2P exit code: $P2P_EXIT"
echo "============================================"
echo ""

exit "$EXIT_CODE"
