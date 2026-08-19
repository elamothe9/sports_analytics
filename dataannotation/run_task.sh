#!/bin/bash
#
# Mini-SWE-Agent Task Runner
#
# Runs mini-swe-agent on a task folder using a specified model.
# Prerequisites: run setup.sh first, Docker Desktop must be running,
# and the task's Docker image must be built (run validate_docker.sh first).
#
# Usage: ./run_task.sh <task_dir> <model> [api_key]
#
#   <task_dir>  - Path to the task folder (must contain prompt.md)
#   <model>     - "test_agent" or "golden"
#   [api_key]   - API key (or set MINI_SWE_API_KEY env var)
#
# Examples:
#   ./run_task.sh ~/tasks/my-task test_agent
#   ./run_task.sh ~/tasks/my-task golden MY_API_KEY
#   MINI_SWE_API_KEY=xxx ./run_task.sh ~/tasks/my-task test_agent
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/patch_utils.sh
source "$SCRIPT_DIR/internal/patch_utils.sh"

TASK_DIR="${1:-}"
MODEL="${2:-}"
API_KEY="${3:-${MINI_SWE_API_KEY:-}}"

VENV_DIR="$HOME/mini-sweagent-env"
CONFIG_DIR="$HOME/mini-sweagent/configs"

# ─────────────────────────────────────────────
# Usage
# ─────────────────────────────────────────────
if [ -z "$TASK_DIR" ] || [ -z "$MODEL" ]; then
    echo ""
    echo "Usage: ./run_task.sh <task_dir> <model> [api_key]"
    echo ""
    echo "  <task_dir>  - Task folder (must contain prompt.md and a built Docker image)"
    echo "  <model>     - 'test_agent' or 'golden'"
    echo "  [api_key]   - API key (or set MINI_SWE_API_KEY env var)"
    echo ""
    echo "Examples:"
    echo "  ./run_task.sh ~/tasks/my-task test_agent"
    echo "  ./run_task.sh ~/tasks/my-task golden MY_API_KEY"
    echo ""
    exit 1
fi

# Validate model choice
if [[ "$MODEL" != "test_agent" && "$MODEL" != "golden" ]]; then
    echo "Error: Model must be 'test_agent' or 'golden', got: $MODEL"
    exit 1
fi

# ─────────────────────────────────────────────
# Resolve paths and validate
# ─────────────────────────────────────────────

# Resolve to absolute path
TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"
if [ -z "$TASK_DIR" ]; then
    echo "Error: Task folder not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"
CONFIG_FILE="$CONFIG_DIR/${MODEL}_config.yaml"

# Check prompt.md exists
if [ ! -f "$TASK_DIR/prompt.md" ]; then
    echo "Error: prompt.md not found in $TASK_DIR"
    echo "Write your task prompt to prompt.md before running the agent."
    exit 1
fi
if grep -qF \
    -e '[Describe what the agent should do]' \
    -e '[Provide relevant context about the codebase]' \
    -e '[List specific requirements]' \
    "$TASK_DIR/prompt.md"; then
    echo "prompt.md still contains placeholders. Please either remove them, or fill them in. Note that the template is just a suggestion - you can format your prompt however you like as long as it meets the requirements laid out in the Task Construction Methodology instructions."
    exit 1
fi

# Check venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: mini-swe-agent environment not found at $VENV_DIR"
    echo "Please run setup.sh first."
    exit 1
fi

# Check config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    echo "Please run setup.sh first."
    exit 1
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running."
    echo "Please start Docker Desktop and try again."
    exit 1
fi

# Check Docker image exists
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Error: Docker image '$IMAGE_NAME' not found."
    echo "Run validate_docker.sh first to build the image."
    exit 1
fi

# Check API key
if [ -z "$API_KEY" ]; then
    echo "Error: No API key provided."
    echo "Pass it as the third argument or set MINI_SWE_API_KEY env var."
    exit 1
fi

# ─────────────────────────────────────────────
# Setup output directories
# ─────────────────────────────────────────────
mkdir -p "$TASK_DIR/trajectories"
mkdir -p "$TASK_DIR/patches"

# ─────────────────────────────────────────────
# Activate venv
# ─────────────────────────────────────────────
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

TRAJECTORY_FILE="$TASK_DIR/trajectories/${MODEL}_trajectory.json"

# Create a task-specific config override with the Docker image.
# The override contains the API key, so make cleanup unconditional.
TASK_CONFIG="$TASK_DIR/.mini_swe_config.yaml"
cleanup_task_config() {
    rm -f "$TASK_CONFIG"
}
trap cleanup_task_config EXIT

CONFIG_VALUES=$(MINI_SWE_CONFIG_API_KEY="$API_KEY" \
    python "$SCRIPT_DIR/internal/run_task_config.py" prepare \
        --config-file "$CONFIG_FILE" \
        --task-config "$TASK_CONFIG" \
        --image-name "$IMAGE_NAME")
MODEL_NAME=$(printf '%s\n' "$CONFIG_VALUES" | sed -n '1p')
MODEL_REQUEST_TIMEOUT_SECONDS=$(printf '%s\n' "$CONFIG_VALUES" | sed -n '2p')
MODEL_REQUEST_RETRIES=$(printf '%s\n' "$CONFIG_VALUES" | sed -n '3p')
MODEL_REQUEST_TOTAL_ATTEMPTS=$(printf '%s\n' "$CONFIG_VALUES" | sed -n '4p')

echo ""
echo "============================================"
echo "  Mini-SWE-Agent Task Runner"
echo "============================================"
echo ""
echo "Task folder:  $TASK_DIR"
echo "Model:        $MODEL ($MODEL_NAME)"
echo "Docker image: $IMAGE_NAME"
echo "Config:       $CONFIG_FILE"
echo "Trajectory:   $TRAJECTORY_FILE"
echo "Timeout:      ${MODEL_REQUEST_TIMEOUT_SECONDS}s per model request"
echo "Retries:      ${MODEL_REQUEST_RETRIES} additional (${MODEL_REQUEST_TOTAL_ATTEMPTS} total attempt(s))"
if [ -n "${ETALON_DOCKER_RUN_ARGS:-}" ]; then
    echo "Docker args:  $ETALON_DOCKER_RUN_ARGS"
fi
echo ""
echo "Starting mini-swe-agent..."
echo ""

# ─────────────────────────────────────────────
# Run mini-swe-agent
# ─────────────────────────────────────────────
# Note: The exact CLI flags may need adjustment based on mini-swe-agent's
# actual interface. Check `mini --help` after install.
#
# Key considerations:
# - We pass the Docker image name so it runs inside the task container
# - We need the container to persist after the run for diff extraction
# - The -y flag auto-confirms prompts, --exit-immediately exits after completion

scrub_api_key_from_file() {
    MINI_SWE_CONFIG_API_KEY="$API_KEY" \
        python "$SCRIPT_DIR/internal/run_task_config.py" scrub "$1"
}

model_timeout_detected() {
    local file
    for file in "$RUN_LOG" "$TRAJECTORY_FILE"; do
        [ -f "$file" ] || continue
        if grep -Eiq 'litellm\.Timeout|APITimeoutError|Connection timed out|Request timed out' "$file"; then
            return 0
        fi
    done
    return 1
}

print_model_timeout_notice() {
    echo ""
    echo "Model request timed out after ${MODEL_REQUEST_TIMEOUT_SECONDS} seconds."
    echo ""
    echo "This is the model/API request timeout, not the Docker command timeout."
    echo "Config file: $CONFIG_FILE"
    echo ""
    echo "To allow longer model thinking time, edit:"
    echo "  worker_tools.model_request_timeout_seconds"
    echo ""
    echo "If the endpoint is flaky, you can also increase:"
    echo "  worker_tools.model_request_retries"
    echo ""
    echo "Keep retries low unless you are seeing intermittent endpoint failures."
    echo "Do not change environment.timeout for model request timeouts; that setting controls Docker command execution inside the task container."
}

RUN_LOG="$TASK_DIR/trajectories/${MODEL}_run.log"
RUN_EXIT=0
TEE_EXIT=0

if [[ "$MODEL" == "test_agent" ]]; then
    # Test agent: fully automated difficulty-calibration run
    set +e
    MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT="$MODEL_REQUEST_TOTAL_ATTEMPTS" mini \
        -c "$TASK_CONFIG" \
        -t "$(cat "$TASK_DIR/prompt.md")" \
        -o "$TRAJECTORY_FILE" \
        -y --exit-immediately \
        2>&1 | tee "$RUN_LOG"
    PIPE_STATUS=("${PIPESTATUS[@]}")
    set -e
else
    # Golden: interactive golden solution derivation
    # Worker can guide the agent and continue the session until solution is correct
    echo "Running in INTERACTIVE mode — you can guide the model to derive the golden solution."
    echo "Review each step and provide feedback as needed."
    echo ""
    set +e
    MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT="$MODEL_REQUEST_TOTAL_ATTEMPTS" mini \
        -c "$TASK_CONFIG" \
        -t "$(cat "$TASK_DIR/prompt.md")" \
        -o "$TRAJECTORY_FILE" \
        2>&1 | tee "$RUN_LOG"
    PIPE_STATUS=("${PIPESTATUS[@]}")
    set -e
fi

RUN_EXIT="${PIPE_STATUS[0]}"
TEE_EXIT="${PIPE_STATUS[1]:-0}"
if [ "$TEE_EXIT" -ne 0 ] && [ "$RUN_EXIT" -eq 0 ]; then
    RUN_EXIT="$TEE_EXIT"
fi

# Clean up the temporary config as soon as the agent process is done.
cleanup_task_config
scrub_api_key_from_file "$TRAJECTORY_FILE"
scrub_api_key_from_file "$RUN_LOG"

if [ $RUN_EXIT -ne 0 ]; then
    echo ""
    echo "WARNING: mini-swe-agent exited with code $RUN_EXIT"
    echo "Check the log: $TASK_DIR/trajectories/${MODEL}_run.log"
    if model_timeout_detected; then
        print_model_timeout_notice
    fi
fi

# ─────────────────────────────────────────────
# Extract diff from trajectory
# ─────────────────────────────────────────────
echo ""
echo "--- Extracting agent diff ---"

# setup.sh patches mini-swe-agent to disable container cleanup,
# so the container should still be alive after the agent finishes.

PATCH_FILE="$TASK_DIR/patches/${MODEL}_patch.diff"
CONTAINER_ID=$(docker ps --filter "ancestor=$IMAGE_NAME" --format '{{.ID}}' | head -n1)

if [ -n "$CONTAINER_ID" ]; then
    echo "Found container: $CONTAINER_ID"

    extract_container_patch "$CONTAINER_ID" "$PATCH_FILE"

    # Clean up the container
    docker stop "$CONTAINER_ID" > /dev/null 2>&1
    docker rm "$CONTAINER_ID" > /dev/null 2>&1
else
    echo "WARNING: No container found for image $IMAGE_NAME"
    echo "The container may have been removed unexpectedly."
    echo "Use extract_patch.sh to replay from the trajectory."
fi

# Report result
if [ -s "$PATCH_FILE" ]; then
    echo "Patch saved: $PATCH_FILE ($(wc -l < "$PATCH_FILE" | tr -d ' ') lines)"
else
    echo "WARNING: No diff extracted. The agent may not have made any code changes."
    echo "Try: ./extract_patch.sh $TASK_DIR $TRAJECTORY_FILE"
fi

echo ""
echo "============================================"
echo "  Done!"
echo "============================================"
echo ""
echo "Outputs:"
echo "  Trajectory: $TRAJECTORY_FILE"
echo "  Run log:    $TASK_DIR/trajectories/${MODEL}_run.log"
[ -f "$TASK_DIR/patches/${MODEL}_patch.diff" ] && \
echo "  Patch:      $TASK_DIR/patches/${MODEL}_patch.diff"
echo ""
echo "Next steps:"
if [[ "$MODEL" == "test_agent" ]]; then
    echo "  1. Review the trajectory and patch"
    echo "  2. Run golden solution: ./run_task.sh $TASK_DIR golden"
    echo "  3. Generate deliverables: ./create_delivery.sh $TASK_DIR"
else
    echo "  1. Review the trajectory and patch"
    echo "  2. Generate deliverables: ./create_delivery.sh $TASK_DIR"
fi
echo ""

if [ "$RUN_EXIT" -ne 0 ]; then
    exit "$RUN_EXIT"
fi
