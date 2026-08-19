#!/bin/bash
#
# Mini-SWE-Agent — One-Time Setup Script
#
# Installs mini-swe-agent via pip, checks Docker, and writes config files.
# Works on macOS and Linux (including WSL).
#
# Usage: ./setup.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/mini-sweagent-env"
CONFIG_DIR="$HOME/mini-sweagent/configs"

echo ""
echo "============================================"
echo "  Mini-SWE-Agent — One-Time Setup"
echo "============================================"
echo ""
echo "This will install mini-swe-agent and its dependencies."
echo "Install location: $VENV_DIR (Python venv)"
echo "Config location:  $CONFIG_DIR"
echo ""

# ─────────────────────────────────────────────
# Step 1: Find or install Python 3.11-3.13
# ─────────────────────────────────────────────
echo "--- Step 1: Checking Python ---"

find_python() {
  for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
      version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -n1)
      major=$(echo "$version" | cut -d. -f1)
      minor=$(echo "$version" | cut -d. -f2)
      if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ] && [ "$minor" -lt 14 ]; then
        echo "$cmd"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_CMD="$(find_python || true)"

if [ -z "${PYTHON_CMD}" ]; then
  echo "Python 3.11-3.13 not found. Attempting to install Python 3.12..."
  echo ""

  if [[ "$(uname)" == "Darwin" ]]; then
    if ! command -v brew &>/dev/null; then
      echo "ERROR: Homebrew is not installed."
      echo "Install it from https://brew.sh then re-run this script."
      exit 1
    fi
    brew install python@3.12
    PYTHON_CMD="python3.12"
  elif [[ "$(uname)" == "Linux" ]]; then
    if command -v apt-get &>/dev/null; then
      sudo apt-get update
      sudo apt-get install -y python3-full python3-venv python3-dev
      if apt-cache show python3.12 >/dev/null 2>&1; then
        sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
        PYTHON_CMD="python3.12"
      else
        PYTHON_CMD="python3"
      fi
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y python3 python3-devel python3-virtualenv || true
      sudo dnf install -y python3.12 python3.12-devel || true
      command -v python3.12 &>/dev/null && PYTHON_CMD="python3.12" || PYTHON_CMD="python3"
    else
      echo "ERROR: Could not detect package manager (apt or dnf)."
      exit 1
    fi
  else
    echo "ERROR: Unsupported OS."
    exit 1
  fi
fi

if ! command -v "$PYTHON_CMD" &>/dev/null; then
  echo "ERROR: Could not find $PYTHON_CMD after installation attempt."
  echo "Install Python 3.11, 3.12, or 3.13, then re-run this script."
  exit 1
fi

if ! "$PYTHON_CMD" "$SCRIPT_DIR/internal/setup_helpers.py" check-python-version --executable-label "$PYTHON_CMD"; then
  exit 1
fi

echo "Using: $PYTHON_CMD ($("$PYTHON_CMD" --version 2>&1))"
echo ""

if ! "$PYTHON_CMD" -m venv --help &>/dev/null; then
  if command -v apt-get &>/dev/null; then
    echo "Python venv module not available for $PYTHON_CMD; installing venv support..."
    sudo apt-get update
    if [[ "$PYTHON_CMD" == python3.12 ]]; then
      sudo apt-get install -y python3.12-venv python3-full
    else
      sudo apt-get install -y python3-venv python3-full
    fi
  fi

  if ! "$PYTHON_CMD" -m venv --help &>/dev/null; then
    echo "ERROR: Python venv module not available for $PYTHON_CMD."
    echo "On Ubuntu/Debian, install the venv package (e.g., python3-venv or python3.12-venv)."
    exit 1
  fi
fi

# ─────────────────────────────────────────────
# Step 2: Create virtual environment
# ─────────────────────────────────────────────
echo "--- Step 2: Creating virtual environment ---"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
  if "$VENV_DIR/bin/python" "$SCRIPT_DIR/internal/setup_helpers.py" check-python-version --quiet
  then
    echo "Virtual environment already exists at $VENV_DIR"
    echo "Reusing existing environment..."
  else
    echo "Existing virtual environment uses an incompatible Python version, removing..."
    rm -rf "$VENV_DIR"
    echo "Creating venv at $VENV_DIR..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
  fi
else
  if [ -d "$VENV_DIR" ]; then
    echo "Found incomplete venv at $VENV_DIR, removing..."
    rm -rf "$VENV_DIR"
  fi
  echo "Creating venv at $VENV_DIR..."
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "Activated venv."
echo "VENV python: $(python "$SCRIPT_DIR/internal/setup_helpers.py" python-executable)"
if ! python "$SCRIPT_DIR/internal/setup_helpers.py" check-python-version --executable-label "$VENV_DIR/bin/python"; then
  exit 1
fi

# Bootstrap pip if missing
if ! python -m pip --version >/dev/null 2>&1; then
  echo "pip not found in venv. Bootstrapping via ensurepip..."
  python -m ensurepip --upgrade
fi

echo "VENV pip:    $(python -m pip -V)"
echo ""

python -m pip install -U pip setuptools wheel

# ─────────────────────────────────────────────
# Step 3: Install mini-swe-agent
# ─────────────────────────────────────────────
echo "--- Step 3: Installing mini-swe-agent ---"

python -m pip install -U mini-swe-agent "litellm>=1.84.0,<2"

echo "mini-swe-agent installed successfully."
echo ""

# Patch: strip provider_specific_fields from API messages
# The DA proxy rejects this field that litellm adds to assistant messages.
SITE_PACKAGES="$(python "$SCRIPT_DIR/internal/setup_helpers.py" site-packages)"
LITELLM_MODEL_FILE="$SITE_PACKAGES/minisweagent/models/litellm_model.py"
if [ -f "$LITELLM_MODEL_FILE" ]; then
  if grep -q '"extra"' "$LITELLM_MODEL_FILE" && ! grep -q 'provider_specific_fields' "$LITELLM_MODEL_FILE"; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' 's/if k != "extra"/if k not in ("extra", "provider_specific_fields")/' "$LITELLM_MODEL_FILE"
    else
      sed -i 's/if k != "extra"/if k not in ("extra", "provider_specific_fields")/' "$LITELLM_MODEL_FILE"
    fi
    echo "Patched litellm_model.py to strip provider_specific_fields from API messages."
  else
    echo "litellm_model.py already patched or has different format — skipping."
  fi
else
  echo "WARNING: Could not locate litellm_model.py for patching."
fi

# Patch 2: Disable container cleanup so we can extract diffs after agent finishes.
# mini-swe-agent destroys the Docker container on exit. We disable this so
# run_task.sh can extract git diff from the live container.
DOCKER_ENV_FILE="$SITE_PACKAGES/minisweagent/environments/docker.py"
if [ -f "$DOCKER_ENV_FILE" ]; then
  if grep -q 'def cleanup' "$DOCKER_ENV_FILE" && ! grep -q 'PATCHED: cleanup disabled' "$DOCKER_ENV_FILE"; then
    python "$SCRIPT_DIR/internal/setup_helpers.py" patch-docker-cleanup --file "$DOCKER_ENV_FILE"
    echo "Patched docker.py to disable container cleanup."
  else
    echo "docker.py already patched or has different format — skipping."
  fi
else
  echo "WARNING: Could not locate docker.py for patching."
fi
echo ""

# Verify the CLI is available
if command -v mini &>/dev/null; then
  echo "CLI check: $(mini --version 2>&1 || echo 'mini command available')"
elif python -m mini_swe_agent --help &>/dev/null 2>&1; then
  echo "CLI check: mini-swe-agent available via python -m"
else
  echo "WARNING: Could not verify mini-swe-agent CLI."
  echo "Try running: source $VENV_DIR/bin/activate && mini --help"
fi

# Pre-create global config so mini doesn't prompt interactively
MINI_GLOBAL_CONFIG_DIR="$HOME/Library/Application Support/mini-swe-agent"
if [[ "$(uname)" == "Linux" ]]; then
  MINI_GLOBAL_CONFIG_DIR="$HOME/.config/mini-swe-agent"
fi
mkdir -p "$MINI_GLOBAL_CONFIG_DIR"
if [ ! -f "$MINI_GLOBAL_CONFIG_DIR/.env" ]; then
  cat > "$MINI_GLOBAL_CONFIG_DIR/.env" << 'DOTENV'
# Global defaults (overridden by task-specific configs)
MSWEA_CONFIGURED="true"
MSWEA_MODEL_NAME="anthropic/claude-sonnet-5"
DOTENV
  echo "Created global config at $MINI_GLOBAL_CONFIG_DIR/.env"
fi
echo ""

# ─────────────────────────────────────────────
# Step 4: Check Docker
# ─────────────────────────────────────────────
echo "--- Step 4: Checking Docker ---"

if command -v docker &>/dev/null; then
  if docker info &>/dev/null 2>&1; then
    echo "Docker is installed and running."
  else
    echo "Docker is installed but NOT running."
    echo "Please start Docker Desktop before running tasks."
  fi
else
  echo "WARNING: Docker is not installed."
  echo "mini-swe-agent needs Docker to run code in sandboxed containers."
  echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
fi
echo ""

# ─────────────────────────────────────────────
# Step 5: Write config files
# ─────────────────────────────────────────────
echo "--- Step 5: Setting up config files ---"

mkdir -p "$CONFIG_DIR"

# Copy configs from the worker_tools distribution
cp "$SCRIPT_DIR/configs/test_agent_config.yaml" "$CONFIG_DIR/test_agent_config.yaml"
echo "Copied test_agent_config.yaml to $CONFIG_DIR/"

cp "$SCRIPT_DIR/configs/golden_config.yaml" "$CONFIG_DIR/golden_config.yaml"
echo "Copied golden_config.yaml to $CONFIG_DIR/"

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "Installed:"
echo "  Python venv:     $VENV_DIR"
echo "  mini-swe-agent:  $(python -m pip show mini-swe-agent 2>/dev/null | grep Version || echo 'installed')"
echo "  Configs:         $CONFIG_DIR"
echo ""
echo "Next steps:"
echo "  1. Make sure Docker Desktop is running"
echo "  2. Clone a repo:  ./download_repo.sh <github_url> <40-character-commit-sha>"
echo "  3. Edit the Dockerfile, write your prompt and tests"
echo "  4. Validate:      ./validate_docker.sh <task_dir>"
echo "  5. Run agent:     ./run_task.sh <task_dir> test_agent"
echo ""
