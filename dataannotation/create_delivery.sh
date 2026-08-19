#!/bin/bash
#
# Create Delivery — Package SWE-bench-style Etalon deliverables.
#
# Collects patches, packages hidden tests, emits instance.json, and creates a
# delivery ZIP with raw files as a backup.
#
# Usage: ./create_delivery.sh <task_dir>
#
# Expected state:
#   - run_task.sh has been run with test_agent, producing test_agent_patch.diff
#   - a golden solution patch exists at patches/golden_patch.diff
#   - .dockerignore hides golden_tests/ from Docker builds
#   - golden_tests/run_tests_f2p.sh and run_tests_p2p.sh are present
#

set -euo pipefail

TASK_DIR="${1:-}"
F2P_ENTRYPOINT="golden_tests/run_tests_f2p.sh"
P2P_ENTRYPOINT="golden_tests/run_tests_p2p.sh"
F2P_SCRIPT="run_tests_f2p.sh"
P2P_SCRIPT="run_tests_p2p.sh"

if [ -z "$TASK_DIR" ]; then
    echo ""
    echo "Usage: ./create_delivery.sh <task_dir>"
    echo ""
    exit 1
fi

command -v zip >/dev/null 2>&1 || {
    echo "ERROR: 'zip' command not found. Please install it (e.g., apt-get install zip)."
    exit 1
}

TASK_DIR="$(cd "$TASK_DIR" 2>/dev/null && pwd)"
if [ -z "$TASK_DIR" ]; then
    echo "Error: Task directory not found."
    exit 1
fi

TASK_NAME="$(basename "$TASK_DIR")"
PATCHES_DIR="$TASK_DIR/patches"
mkdir -p "$PATCHES_DIR"

has_required_entrypoints() {
    local tests_dir="$1"
    [ -f "$tests_dir/$F2P_SCRIPT" ] && [ -f "$tests_dir/$P2P_SCRIPT" ]
}

GOLDEN_TESTS_DIR="$TASK_DIR/golden_tests"
if ! has_required_entrypoints "$GOLDEN_TESTS_DIR"; then
    GOLDEN_TESTS_DIR="$PATCHES_DIR/golden_tests_backup"
fi

echo ""
echo "============================================"
echo "  Generate SWE-bench-Style Deliverables"
echo "============================================"
echo ""
echo "Task directory: $TASK_DIR"
echo ""

echo "--- Checking deliverables ---"
echo ""

MISSING=0

AGENT_PATCH="$PATCHES_DIR/test_agent_patch.diff"
if [ -f "$AGENT_PATCH" ] && [ -s "$AGENT_PATCH" ]; then
    echo "  Test-agent patch:        OK ($(wc -l < "$AGENT_PATCH" | tr -d ' ') lines)"
else
    echo "  Test-agent patch:        MISSING"
    echo "    Run: ./run_task.sh $TASK_DIR test_agent"
    MISSING=$((MISSING + 1))
fi

GOLDEN_PATCH="$PATCHES_DIR/golden_patch.diff"
if [ -f "$GOLDEN_PATCH" ] && [ -s "$GOLDEN_PATCH" ]; then
    echo "  Golden patch:            OK ($(wc -l < "$GOLDEN_PATCH" | tr -d ' ') lines)"
else
    echo "  Golden patch:            MISSING"
    echo "    Derive golden solution, save as: $PATCHES_DIR/golden_patch.diff"
    MISSING=$((MISSING + 1))
fi

PROMPT_FILE="$TASK_DIR/prompt.md"
if [ -f "$PROMPT_FILE" ] && [ -s "$PROMPT_FILE" ]; then
    echo "  Prompt:                  OK"
    PROMPT_CONTENT=$(cat "$PROMPT_FILE")
    if echo "$PROMPT_CONTENT" | grep -qF '<!-- '; then
        echo "WARNING: template placeholder found in prompt.md: HTML comment block" >&2
    fi
    if echo "$PROMPT_CONTENT" | grep -qF '[Describe '; then
        echo "WARNING: template placeholder found in prompt.md: [Describe ...] block" >&2
    fi
    if echo "$PROMPT_CONTENT" | grep -qF '[Provide '; then
        echo "WARNING: template placeholder found in prompt.md: [Provide ...] block" >&2
    fi
    if echo "$PROMPT_CONTENT" | grep -qF '[List '; then
        echo "WARNING: template placeholder found in prompt.md: [List ...] block" >&2
    fi
else
    echo "  Prompt:                  MISSING"
    MISSING=$((MISSING + 1))
fi

METADATA_FILE="$TASK_DIR/.task_metadata.json"
if [ -f "$METADATA_FILE" ]; then
    echo "  Task metadata:           OK"
else
    echo "  Task metadata:           MISSING (run download_repo.sh)"
    MISSING=$((MISSING + 1))
fi

TEST_AGENT_TRAJ="$TASK_DIR/trajectories/test_agent_trajectory.json"
GOLDEN_TRAJ="$TASK_DIR/trajectories/golden_trajectory.json"
[ -f "$TEST_AGENT_TRAJ" ] && echo "  Test-agent trajectory:   OK" || echo "  Test-agent trajectory:   MISSING"
[ -f "$GOLDEN_TRAJ" ] && echo "  Golden trajectory:       OK" || echo "  Golden trajectory:       (not run)"

echo ""

if [ "$MISSING" -gt 0 ]; then
    echo "ERROR: $MISSING required deliverable(s) missing."
    echo "DELIVERY ABORTED: Fix the missing deliverables above before generating output."
    echo ""
    exit 1
fi

echo "--- Validating golden test entrypoints ---"
VALIDATION_FAILED=false

if has_required_entrypoints "$GOLDEN_TESTS_DIR"; then
    echo "  F2P entrypoint:          OK ($GOLDEN_TESTS_DIR/$F2P_SCRIPT)"
    echo "  P2P entrypoint:          OK ($GOLDEN_TESTS_DIR/$P2P_SCRIPT)"
    if ! bash -n "$GOLDEN_TESTS_DIR/$F2P_SCRIPT"; then
        echo "ERROR: $F2P_SCRIPT has shell syntax errors."
        VALIDATION_FAILED=true
    fi
    if ! bash -n "$GOLDEN_TESTS_DIR/$P2P_SCRIPT"; then
        echo "ERROR: $P2P_SCRIPT has shell syntax errors."
        VALIDATION_FAILED=true
    fi
else
    echo "ERROR: Required golden test entrypoints not found."
    echo "Expected:"
    echo "  $TASK_DIR/$F2P_ENTRYPOINT"
    echo "  $TASK_DIR/$P2P_ENTRYPOINT"
    echo "Checked: $TASK_DIR/golden_tests/ and $PATCHES_DIR/golden_tests_backup/"
    VALIDATION_FAILED=true
fi

if [ "$VALIDATION_FAILED" = true ]; then
    echo ""
    echo "DELIVERY ABORTED: Fix the issues above before generating deliverables."
    echo ""
    exit 1
fi

echo "  Entry validation:        OK"
echo ""

echo "--- Generating hidden test patch ---"
TEST_PATCH="$PATCHES_DIR/test_patch.diff"
TEMP_GIT_DIR=$(mktemp -d)

mkdir -p "$TEMP_GIT_DIR/golden_tests"
cp -a "$GOLDEN_TESTS_DIR/." "$TEMP_GIT_DIR/golden_tests/"
(
    cd "$TEMP_GIT_DIR"
    git init -q
    git add -A golden_tests
    git diff --cached
) > "$TEST_PATCH"
rm -rf "$TEMP_GIT_DIR"

if [ -f "$TEST_PATCH" ] && [ -s "$TEST_PATCH" ]; then
    echo "  Test patch:              OK ($(wc -l < "$TEST_PATCH" | tr -d ' ') lines)"
else
    echo "  Test patch:              MISSING"
    echo "    No golden test content found to generate test patch from."
    exit 1
fi

echo ""
echo "--- Generating SWE-bench-style instance.json ---"

SUMMARY_FILE="$PATCHES_DIR/instance.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/internal/task_artifacts.py" write-instance \
    --task-dir "$TASK_DIR" \
    --task-name "$TASK_NAME" \
    --patches-dir "$PATCHES_DIR" \
    --f2p-entrypoint "$F2P_ENTRYPOINT" \
    --p2p-entrypoint "$P2P_ENTRYPOINT"

echo ""
echo "Output written to: $SUMMARY_FILE"

echo "--- Creating delivery ZIP ---"

DELIVERY_ZIP="$TASK_DIR/delivery_${TASK_NAME}.zip"
rm -f "$DELIVERY_ZIP"

ZIP_FILES=()
[ -f "$PATCHES_DIR/instance.json" ] && ZIP_FILES+=("patches/instance.json")
[ -f "$AGENT_PATCH" ] && ZIP_FILES+=("patches/test_agent_patch.diff")
[ -f "$GOLDEN_PATCH" ] && ZIP_FILES+=("patches/golden_patch.diff")
[ -f "$TEST_PATCH" ] && ZIP_FILES+=("patches/test_patch.diff")
[ -f "$TASK_DIR/prompt.md" ] && ZIP_FILES+=("prompt.md")
[ -f "$TASK_DIR/.task_metadata.json" ] && ZIP_FILES+=(".task_metadata.json")
[ -f "$TASK_DIR/Dockerfile" ] && ZIP_FILES+=("Dockerfile")
[ -f "$TASK_DIR/.dockerignore" ] && ZIP_FILES+=(".dockerignore")
[ -f "$TASK_DIR/.gitignore" ] && ZIP_FILES+=(".gitignore")

if [ "$GOLDEN_TESTS_DIR" = "$TASK_DIR/golden_tests" ]; then
    while IFS= read -r -d '' f; do
        ZIP_FILES+=("${f#$TASK_DIR/}")
    done < <(find "$GOLDEN_TESTS_DIR" -type f -print0 | sort -z)
fi

(cd "$TASK_DIR" && zip -q "$DELIVERY_ZIP" "${ZIP_FILES[@]}" 2>/dev/null) || true

if [ "$GOLDEN_TESTS_DIR" != "$TASK_DIR/golden_tests" ]; then
    GOLDEN_ZIP_TMPDIR=$(mktemp -d)
    mkdir -p "$GOLDEN_ZIP_TMPDIR/golden_tests"
    cp -a "$GOLDEN_TESTS_DIR/." "$GOLDEN_ZIP_TMPDIR/golden_tests/"
    (cd "$GOLDEN_ZIP_TMPDIR" && zip -q -g -r "$DELIVERY_ZIP" golden_tests 2>/dev/null) || true
    rm -rf "$GOLDEN_ZIP_TMPDIR"
fi

PII_SCRUB_TMPDIR=$(mktemp -d)
TRAJ_ADDED=false
if [ -f "$TEST_AGENT_TRAJ" ]; then
    mkdir -p "$PII_SCRUB_TMPDIR/trajectories"
    sed -E 's|/home/[a-zA-Z0-9_]+/|/workspace/|g; s|/Users/[a-zA-Z0-9_]+/|/workspace/|g' \
        "$TEST_AGENT_TRAJ" | \
        sed -E 's/"api_key"[[:space:]]*:[[:space:]]*"[^"]*"/"api_key": "<redacted>"/g' \
        > "$PII_SCRUB_TMPDIR/trajectories/test_agent_trajectory.json"
    TRAJ_ADDED=true
fi
if [ -f "$GOLDEN_TRAJ" ]; then
    mkdir -p "$PII_SCRUB_TMPDIR/trajectories"
    sed -E 's|/home/[a-zA-Z0-9_]+/|/workspace/|g; s|/Users/[a-zA-Z0-9_]+/|/workspace/|g' \
        "$GOLDEN_TRAJ" | \
        sed -E 's/"api_key"[[:space:]]*:[[:space:]]*"[^"]*"/"api_key": "<redacted>"/g' \
        > "$PII_SCRUB_TMPDIR/trajectories/golden_trajectory.json"
    TRAJ_ADDED=true
fi
if [ "$TRAJ_ADDED" = true ]; then
    (cd "$PII_SCRUB_TMPDIR" && zip -q -g "$DELIVERY_ZIP" trajectories/*.json 2>/dev/null) || true
fi
rm -rf "$PII_SCRUB_TMPDIR"

if [ -f "$DELIVERY_ZIP" ]; then
    ZIP_SIZE=$(du -h "$DELIVERY_ZIP" | cut -f1 | tr -d ' ')
    echo "Delivery ZIP: $DELIVERY_ZIP ($ZIP_SIZE)"
else
    echo "WARNING: Could not create delivery ZIP."
fi

echo ""
echo "============================================"
echo "  Delivery Complete"
echo "============================================"
echo ""
echo "Files:"
echo "  instance.json             — SWE-bench-style format"
[ -f "$AGENT_PATCH" ] && echo "  test_agent_patch.diff     — Test-agent solution"
[ -f "$GOLDEN_PATCH" ] && echo "  golden_patch.diff         — Golden solution"
[ -f "$TEST_PATCH" ] && echo "  test_patch.diff           — Hidden test patch"
echo ""
[ -f "$DELIVERY_ZIP" ] && echo "Delivery ZIP: $DELIVERY_ZIP"
echo ""
