#!/bin/bash
#
# Download Repo — Fetch + scaffold Docker templates
#
# Fetches a GitHub repo at a specific commit and sets up the task directory
# with Dockerfile, build/run scripts, and placeholder files.
#
# Usage: ./download_repo.sh <github_url> <commit_sha> [target_dir]
#
#   <github_url>  - GitHub clone URL (HTTPS or SSH)
#   <commit_sha>  - Full 40-character commit SHA to checkout
#   [target_dir]  - Optional target directory name (defaults to repo name)
#
# Examples:
#   ./download_repo.sh https://github.com/user/repo.git 0123456789abcdef0123456789abcdef01234567
#   ./download_repo.sh https://github.com/user/repo.git 0123456789abcdef0123456789abcdef01234567 my-task
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GITHUB_URL="${1:-}"
COMMIT_SHA="${2:-}"
TARGET_DIR="${3:-}"

normalize_clone_url_for_docker() {
    local url="$1"
    if [[ "$url" =~ ^git@github.com:(.+)$ ]]; then
        printf 'https://github.com/%s\n' "${BASH_REMATCH[1]}"
    else
        printf '%s\n' "$url"
    fi
}

# ─────────────────────────────────────────────
# Usage
# ─────────────────────────────────────────────
if [ -z "$GITHUB_URL" ] || [ -z "$COMMIT_SHA" ]; then
    echo ""
    echo "Usage: ./download_repo.sh <github_url> <commit_sha> [target_dir]"
    echo ""
    echo "  <github_url>  - GitHub clone URL"
    echo "  <commit_sha>  - Full 40-character commit SHA to checkout"
    echo "  [target_dir]  - Optional target directory name"
    echo ""
    echo "Example:"
    echo "  ./download_repo.sh https://github.com/psf/requests.git 0123456789abcdef0123456789abcdef01234567"
    echo ""
    exit 1
fi

if [[ ! "$COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Error: commit must be a full 40-character SHA."
    echo "Short SHAs are not supported because the tools use shallow fetch."
    exit 1
fi

# ─────────────────────────────────────────────
# Derive target directory from repo URL if not provided
# ─────────────────────────────────────────────
if [ -z "$TARGET_DIR" ]; then
    # Extract repo name from URL: https://github.com/user/repo.git -> repo
    TARGET_DIR=$(basename "$GITHUB_URL" .git)
fi

if [ -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' already exists."
    echo "Remove it first or specify a different target directory."
    exit 1
fi

# ─────────────────────────────────────────────
# Fetch and checkout
# ─────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Download Repo"
echo "============================================"
echo ""
echo "Repository:  $GITHUB_URL"
echo "Commit:      $COMMIT_SHA"
echo "Target:      $TARGET_DIR"
echo ""

echo "--- Fetching base commit ---"
mkdir "$TARGET_DIR"

cd "$TARGET_DIR"
git init -q
git remote add origin "$GITHUB_URL"
git fetch --depth 1 origin "$COMMIT_SHA"
git checkout --detach "$COMMIT_SHA"

# Save metadata before removing .git (needed for SWE-bench format output)
FULL_COMMIT=$(git rev-parse HEAD)
# Extract "owner/repo" from URL: https://github.com/owner/repo.git -> owner/repo
REPO_SLUG=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
DOCKER_REPO_URL=$(normalize_clone_url_for_docker "$GITHUB_URL")
cat > .task_metadata.json << METAEOF
{
  "repo": "$REPO_SLUG",
  "base_commit": "$FULL_COMMIT",
  "github_url": "$GITHUB_URL",
  "docker_repo_url": "$DOCKER_REPO_URL"
}
METAEOF
echo "  Saved task metadata"

# Remove .git to start fresh (the Dockerfile will create its own git repo)
rm -rf .git

echo ""

# ─────────────────────────────────────────────
# Scaffold task structure
# ─────────────────────────────────────────────
echo "--- Setting up task structure ---"

# Copy templates
cp "$SCRIPT_DIR/templates/Dockerfile.template" ./Dockerfile
python3 "$SCRIPT_DIR/internal/task_artifacts.py" render-dockerfile \
    --dockerfile Dockerfile \
    --repo-url "$DOCKER_REPO_URL" \
    --base-commit "$FULL_COMMIT"
echo "  Created Dockerfile"

cp "$SCRIPT_DIR/templates/build_docker.sh.template" ./build_docker.sh
chmod +x ./build_docker.sh
echo "  Created build_docker.sh"

cp "$SCRIPT_DIR/templates/run_docker.sh.template" ./run_docker.sh
chmod +x ./run_docker.sh
echo "  Created run_docker.sh"

# Create golden_tests directory with the required shell entrypoints
mkdir -p golden_tests
cat > golden_tests/README.md << 'GTEOF'
# Golden Tests

This directory is hidden from the agent during task runs.

Required entrypoints:

- `run_tests_f2p.sh` — runs all Fail-to-Pass checks. It must fail before the
  correct solution is applied and pass after the solution is applied.
- `run_tests_p2p.sh` — runs all Pass-to-Pass/regression checks. It must pass
  before and after the solution is applied.

The scripts may call any language or framework internally. The tooling only
checks their shell exit codes.
GTEOF

cat > golden_tests/run_tests_f2p.sh << 'F2PEOF'
#!/usr/bin/env bash
set -euo pipefail

echo "Replace this placeholder with fail-to-pass checks." >&2
exit 1
F2PEOF

cat > golden_tests/run_tests_p2p.sh << 'P2PEOF'
#!/usr/bin/env bash
set -euo pipefail

echo "Replace this placeholder with pass-to-pass/regression checks." >&2
exit 1
P2PEOF

chmod +x golden_tests/run_tests_f2p.sh golden_tests/run_tests_p2p.sh
echo "  Created golden_tests/ (with required entrypoint scripts)"

# Create prompt placeholder
cat > prompt.md << 'EOF'
Do not install any additional dependencies or use online connectivity while working on this task. You must work offline without internet access.

# Task

[Describe what the agent should do]

## Context

[Provide relevant context about the codebase]

## Requirements

[List specific requirements]
EOF
echo "  Created prompt.md (placeholder)"

# Preserve repository ignore behavior while adding worker-side artifacts.
append_ignore_entry() {
    local file="$1"
    local entry="$2"
    touch "$file"
    if ! grep -qxF "$entry" "$file"; then
        printf '%s\n' "$entry" >> "$file"
    fi
}

if [ ! -f .gitignore ]; then
    cat > .gitignore << 'EOF'
# Agent outputs
EOF
else
    printf '\n# Agent outputs\n' >> .gitignore
fi
append_ignore_entry .gitignore "trajectories/"
append_ignore_entry .gitignore "patches/"
append_ignore_entry .gitignore ".mini_swe_config.yaml"
append_ignore_entry .gitignore "*.log"
echo "  Updated .gitignore"

# Create/update .dockerignore to prevent leaking hidden tests and outputs into
# any accidental local-context build. The supported build path uses only the
# Dockerfile and .dockerignore, and the Dockerfile fetches the source itself.
if [ ! -f .dockerignore ]; then
    cat > .dockerignore << 'EOF'
# Prevent agent from seeing hidden tests and worker outputs
EOF
else
    printf '\n# Etalon worker-side artifacts\n' >> .dockerignore
fi
append_ignore_entry .dockerignore "patches/"
append_ignore_entry .dockerignore "trajectories/"
append_ignore_entry .dockerignore "golden_tests/"
append_ignore_entry .dockerignore ".mini_swe_config.yaml"
append_ignore_entry .dockerignore ".dockerignore"
append_ignore_entry .dockerignore "*.log"
append_ignore_entry .dockerignore "Dockerfile"
append_ignore_entry .dockerignore "build_docker.sh"
append_ignore_entry .dockerignore "run_docker.sh"
append_ignore_entry .dockerignore "prompt.md"
append_ignore_entry .dockerignore ".task_metadata.json"
echo "  Updated .dockerignore"

echo ""
echo "============================================"
echo "  Repo downloaded and scaffolded!"
echo "============================================"
echo ""
echo "Directory: $(pwd)"
echo ""
echo "Files created:"
echo "  Dockerfile        - Edit this to set up the build environment"
echo "  build_docker.sh   - Builds the Docker image"
echo "  run_docker.sh     - Runs an interactive shell in the container"
echo "  golden_tests/     - Put hidden test scripts and support files here"
echo "  prompt.md         - Write the agent's task prompt here"
echo ""
echo "Next steps:"
echo "  1. Edit the Dockerfile to install project dependencies"
echo "  2. Write your task prompt in prompt.md"
echo "  3. Fill in golden_tests/run_tests_f2p.sh and run_tests_p2p.sh"
echo "  4. Run: cd $TARGET_DIR && ../validate_docker.sh ."
echo "  5. Run: ../verify_task_state.sh . pre-edit"
echo ""
