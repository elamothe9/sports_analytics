#!/usr/bin/env bash

# Shared Docker runtime arguments for task containers.
# Use simple space-separated flags, for example:
#   export ETALON_DOCKER_RUN_ARGS="--gpus=all"

ETALON_DOCKER_RUN_ARGS_ARRAY=()

load_etalon_docker_run_args() {
    ETALON_DOCKER_RUN_ARGS_ARRAY=()
    if [ -n "${ETALON_DOCKER_RUN_ARGS:-}" ]; then
        read -r -a ETALON_DOCKER_RUN_ARGS_ARRAY <<< "$ETALON_DOCKER_RUN_ARGS"
    fi
}

print_etalon_docker_run_args() {
    if [ "${#ETALON_DOCKER_RUN_ARGS_ARRAY[@]}" -gt 0 ]; then
        echo "Docker run args: ${ETALON_DOCKER_RUN_ARGS_ARRAY[*]}"
    fi
}

docker_run_detached() {
    local args=(-d)
    if [ "${#ETALON_DOCKER_RUN_ARGS_ARRAY[@]}" -gt 0 ]; then
        args+=("${ETALON_DOCKER_RUN_ARGS_ARRAY[@]}")
    fi
    docker run "${args[@]}" "$@"
}
