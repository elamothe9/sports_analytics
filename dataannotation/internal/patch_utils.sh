#!/bin/bash
#
# Shared patch extraction helpers for worker containers.

# Exclude Python bytecode/cache files from every extracted patch. Keep this as a
# shell fragment because it is passed through docker exec bash -c.
PATCH_DIFF_PATHSPEC="-- . ':(exclude)__pycache__' ':(exclude)*.pyc' ':(exclude)**/__pycache__'"

extract_container_patch() {
    local container="$1"
    local output_file="$2"
    local base_sha

    echo "  Staging container changes for extraction..."
    docker exec "$container" bash -c "cd /app && git add -A $PATCH_DIFF_PATHSPEC" >/dev/null 2>&1 || true

    base_sha="$(docker exec "$container" cat /etc/etalon_base_commit 2>/dev/null || true)"
    if [ -z "$base_sha" ]; then
        base_sha="$(docker exec "$container" printenv ETALON_BASE_COMMIT 2>/dev/null || true)"
    fi
    if [ -z "$base_sha" ]; then
        base_sha="$(docker exec "$container" git -C /app rev-list --max-parents=0 HEAD 2>/dev/null | head -n1 || true)"
    fi

    if [ -n "$base_sha" ]; then
        docker exec "$container" bash -c "cd /app && git diff '$base_sha' $PATCH_DIFF_PATHSPEC" > "$output_file" 2>/dev/null || true
    fi

    if [ ! -s "$output_file" ]; then
        echo "  No diff from base commit, checking HEAD..."
        docker exec "$container" bash -c "cd /app && git diff HEAD $PATCH_DIFF_PATHSPEC" > "$output_file" 2>/dev/null || true
    fi

    if [ -s "$output_file" ] && ! head -1 "$output_file" | grep -q "^diff \|^---"; then
        > "$output_file"
    fi
}
