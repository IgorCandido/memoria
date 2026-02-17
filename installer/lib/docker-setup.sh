#!/usr/bin/env bash
# docker-setup.sh — ChromaDB Docker container lifecycle management
# Start, stop, check, and health-check the ChromaDB container

CHROMADB_CONTAINER_NAME="memoria-chromadb"
CHROMADB_HOST_PORT=8001
CHROMADB_CONTAINER_PORT=8000
CHROMADB_IMAGE="chromadb/chroma:latest"
CHROMADB_HEALTH_TIMEOUT=30

# Check if Docker daemon is running
check_docker_running() {
    if ! docker info &>/dev/null; then
        return 1
    fi
    return 0
}

# Check if the ChromaDB container exists (running or stopped)
check_container_exists() {
    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CHROMADB_CONTAINER_NAME}$"
}

# Check if the ChromaDB container is running
check_container_running() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CHROMADB_CONTAINER_NAME}$"
}

# Start ChromaDB container
# Args: $1 = data volume path (default: ~/.local/share/memoria/chroma_data)
start_chromadb_container() {
    local data_path="${1:-${HOME}/.local/share/memoria/chroma_data}"

    # Create data directory if needed
    mkdir -p "$data_path"

    # If container exists but is stopped, start it
    if check_container_exists && ! check_container_running; then
        docker start "$CHROMADB_CONTAINER_NAME" &>/dev/null
        return $?
    fi

    # If already running, nothing to do
    if check_container_running; then
        return 0
    fi

    # Create and start new container
    docker run -d \
        --name "$CHROMADB_CONTAINER_NAME" \
        --restart unless-stopped \
        -p "${CHROMADB_HOST_PORT}:${CHROMADB_CONTAINER_PORT}" \
        -v "${data_path}:/data" \
        -e CHROMA_SERVER_HOST=0.0.0.0 \
        -e CHROMA_SERVER_HTTP_PORT="${CHROMADB_CONTAINER_PORT}" \
        -e IS_PERSISTENT=TRUE \
        "$CHROMADB_IMAGE" \
        &>/dev/null
}

# Stop ChromaDB container
stop_chromadb_container() {
    if check_container_running; then
        docker stop "$CHROMADB_CONTAINER_NAME" &>/dev/null
    fi
}

# Remove ChromaDB container (must be stopped first)
remove_chromadb_container() {
    stop_chromadb_container
    if check_container_exists; then
        docker rm "$CHROMADB_CONTAINER_NAME" &>/dev/null
    fi
}

# Wait for ChromaDB to be healthy (TCP probe)
wait_for_chromadb_healthy() {
    local timeout="${1:-$CHROMADB_HEALTH_TIMEOUT}"
    local elapsed=0

    while [[ "$elapsed" -lt "$timeout" ]]; do
        # TCP probe on the host port
        if bash -c "echo >/dev/tcp/localhost/${CHROMADB_HOST_PORT}" 2>/dev/null; then
            return 0
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}
