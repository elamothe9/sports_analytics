#!/bin/bash
#
# Validate Docker — Build and verify the task's Docker image
#
# Builds the Docker image under the Dockerfile-only contract, starts a
# container, verifies it gets a shell, and confirms /app is checked out at the
# assigned base commit.
#
# Usage: ./validate_docker.sh [task_dir]
#
#   [task_dir]  - Path to task directory (defaults to current directory)
#
# Examples:
#   ./validate_docker.sh ~/tasks/my-task
#   cd ~/tasks/my-task && ../../validate_docker.sh
#

set -euo pipefail

TASK_DIR="${1:-.}"
CONTAINER_ID=""
TEMP_CONTEXT=""

# Resolve to absolute path
TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"
if [ -z "$TASK_DIR" ]; then
    echo "Error: Task directory not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
IMAGE_NAME="sweagent-task-${TASK_NAME}"

cleanup() {
    if [ -n "$CONTAINER_ID" ]; then
        docker stop "$CONTAINER_ID" > /dev/null 2>&1 || true
        docker rm "$CONTAINER_ID" > /dev/null 2>&1 || true
    fi
    if [ -n "$TEMP_CONTEXT" ] && [ -d "$TEMP_CONTEXT" ]; then
        rm -rf "$TEMP_CONTEXT"
    fi
}
trap cleanup EXIT

reject_local_context_instructions() {
    local dockerfile="$1"
    local line_num=0
    shopt -s nocasematch
    while IFS= read -r line; do
        line_num=$((line_num + 1))
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        if [[ "$line" =~ ^[[:space:]]*(COPY|ADD)([[:space:]]|$) ]]; then
            [[ "$line" =~ --from= ]] && continue
            [[ "$line" =~ ^[[:space:]]*ADD([[:space:]]+--[^[:space:]]+)*[[:space:]]+https?:// ]] && continue
            echo "Error: Dockerfile depends on local build-context files (line $line_num):"
            echo "  $line"
            echo "Delivery Dockerfiles must fetch the repository inside the image."
            exit 1
        fi
    done < "$dockerfile"
    shopt -u nocasematch
}

print_run_docker_hint() {
    if [ -x "$TASK_DIR/run_docker.sh" ]; then
        echo "For an interactive shell in this image, run:"
        echo "  cd $TASK_DIR && ./run_docker.sh"
    fi
}

validate_clean_app_checkout() {
    local status_output
    local repo_changes
    local untracked_changes
    status_output=$(docker exec "$CONTAINER_ID" git -C /app status --porcelain --untracked-files=all 2>/dev/null || true)
    if [ -n "$status_output" ]; then
        repo_changes=$(printf '%s\n' "$status_output" | grep -Ev '^\?\? ' || true)
        untracked_changes=$(printf '%s\n' "$status_output" | grep -E '^\?\? ' || true)

        if [ -n "$repo_changes" ] && [ -n "$untracked_changes" ]; then
            echo "Error: Dockerfile setup created or modified files inside /app."
        elif [ -n "$repo_changes" ]; then
            echo "Error: Dockerfile setup modified repository files inside /app."
        else
            echo "Error: Dockerfile setup created files inside /app."
        fi
        echo ""
        echo "The /app directory must remain a clean checkout of the pre-edit codebase after Dockerfile setup."
        echo "Use Dockerfile setup to install tools and dependencies without changing the repository checkout."
        echo "Patch extraction treats changes under /app as solution changes."
        echo ""
        if [ -n "$repo_changes" ]; then
            echo "If a package manager changed repository files during setup, use an install mode that does not rewrite project files."
            echo "Do not commit these changes inside the Dockerfile or change patch extraction to hide them."
            echo "If repository files must change to solve the task, make that part of the golden solution patch."
            echo ""
        fi
        if [ -n "$untracked_changes" ]; then
            echo "Move setup artifacts outside /app. For Python virtualenvs, use a path such as /venv instead of creating the environment inside the repository."
            echo ""
        fi
        echo ""
        echo "First changed paths:"
        printf '%s\n' "$status_output" | sed -n '1,20p'
        echo ""
        print_run_docker_hint
        exit 1
    fi
}

echo ""
echo "============================================"
echo "  Validate Docker"
echo "============================================"
echo ""
echo "Task directory: $TASK_DIR"
echo "Image name:     $IMAGE_NAME"
echo ""

# ─────────────────────────────────────────────
# Check prerequisites
# ─────────────────────────────────────────────
if [ ! -f "$TASK_DIR/Dockerfile" ]; then
    echo "Error: No Dockerfile found in $TASK_DIR"
    echo "Run download_repo.sh first to scaffold the task."
    exit 1
fi

if [ ! -f "$TASK_DIR/.task_metadata.json" ]; then
    echo "Error: No .task_metadata.json found in $TASK_DIR"
    echo "Run download_repo.sh first so the base commit is recorded."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/docker_run_args.sh
source "$SCRIPT_DIR/internal/docker_run_args.sh"

load_etalon_docker_run_args
EXPECTED_COMMIT=$(python3 "$SCRIPT_DIR/internal/task_artifacts.py" metadata-field \
    --metadata "$TASK_DIR/.task_metadata.json" \
    --field base_commit)

if [ -z "$EXPECTED_COMMIT" ]; then
    echo "Error: .task_metadata.json does not contain base_commit."
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running."
    echo "Please start Docker Desktop and try again."
    exit 1
fi

# ─────────────────────────────────────────────
# Step 1: Build the image
# ─────────────────────────────────────────────
echo "--- Step 1: Building Docker image ---"

reject_local_context_instructions "$TASK_DIR/Dockerfile"

TEMP_CONTEXT="$(mktemp -d)"
cp "$TASK_DIR/Dockerfile" "$TEMP_CONTEXT/Dockerfile"
if [ -f "$TASK_DIR/.dockerignore" ]; then
    cp "$TASK_DIR/.dockerignore" "$TEMP_CONTEXT/.dockerignore"
fi

docker build -t "$IMAGE_NAME" "$TEMP_CONTEXT"

echo ""
echo "Build: OK"
echo ""

# ─────────────────────────────────────────────
# Step 2: Start container in detached mode
# ─────────────────────────────────────────────
echo "--- Step 2: Testing container startup ---"

print_etalon_docker_run_args
CONTAINER_ID=$(docker_run_detached "$IMAGE_NAME" sleep 30)
echo "Started container: $CONTAINER_ID"

# Give it a moment to initialize
sleep 2

# Check it's still running
if docker ps --filter "id=$CONTAINER_ID" --format '{{.ID}}' | grep -q .; then
    echo "Container is running: OK"
else
    echo "Error: Container exited immediately."
    echo "Check the Dockerfile — the build may succeed but the container crashes on start."
    echo ""
    echo "Container logs:"
    docker logs "$CONTAINER_ID" 2>&1 | tail -20
    echo ""
    print_run_docker_hint
    docker rm "$CONTAINER_ID" > /dev/null 2>&1 || true
    exit 1
fi

# ─────────────────────────────────────────────
# Step 3: Verify shell access and git state
# ─────────────────────────────────────────────
echo ""
echo "--- Step 3: Verifying container environment ---"

# Check we can exec into it
if docker exec "$CONTAINER_ID" echo "shell access OK" > /dev/null 2>&1; then
    echo "Shell access: OK"
else
    echo "Error: Cannot exec into container."
    echo ""
    print_run_docker_hint
    docker stop "$CONTAINER_ID" > /dev/null 2>&1 || true
    docker rm "$CONTAINER_ID" > /dev/null 2>&1 || true
    exit 1
fi

# Check /app exists
if docker exec "$CONTAINER_ID" test -d /app; then
    echo "Working directory /app: OK"
else
    echo "Error: /app directory not found in container."
    echo ""
    print_run_docker_hint
    exit 1
fi

# Check git checkout state
ACTUAL_COMMIT=$(docker exec "$CONTAINER_ID" git -C /app rev-parse HEAD 2>/dev/null || true)
if [ "$ACTUAL_COMMIT" = "$EXPECTED_COMMIT" ]; then
    echo "Git base commit: OK ($ACTUAL_COMMIT)"
    FILE_COUNT=$(docker exec "$CONTAINER_ID" git -C /app ls-files 2>/dev/null | wc -l | tr -d ' ')
    echo "Files tracked: $FILE_COUNT"
else
    echo "Error: /app is not checked out at the assigned base commit."
    echo "Expected: $EXPECTED_COMMIT"
    echo "Actual:   ${ACTUAL_COMMIT:-<not a git checkout>}"
    echo ""
    print_run_docker_hint
    exit 1
fi

validate_clean_app_checkout
echo "Clean /app checkout: OK"

IMAGE_COMMIT=$(docker exec "$CONTAINER_ID" cat /etc/etalon_base_commit 2>/dev/null || true)
if [ "$IMAGE_COMMIT" = "$EXPECTED_COMMIT" ]; then
    echo "Image base commit marker: OK"
else
    echo "Warning: /etc/etalon_base_commit missing or does not match."
fi

# ─────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────
echo ""
echo "--- Cleanup ---"
docker stop "$CONTAINER_ID" > /dev/null 2>&1
docker rm "$CONTAINER_ID" > /dev/null 2>&1
CONTAINER_ID=""
echo "Test container removed."

echo ""
echo "============================================"
echo "  Validation passed!"
echo "============================================"
echo ""
echo "Docker image '$IMAGE_NAME' is ready."
echo ""
echo "Next steps:"
echo "  1. Fill in golden_tests/run_tests_f2p.sh and run_tests_p2p.sh"
echo "  2. Verify .dockerignore hides golden_tests/ from the build"
echo "  3. Verify pre-edit state: ./verify_task_state.sh $TASK_DIR pre-edit"
echo "  4. Run agent:            ./run_task.sh $TASK_DIR test_agent"
echo ""
print_run_docker_hint
echo ""
