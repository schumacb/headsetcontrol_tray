#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Pipestatus to be non-zero if any command in a pipeline fails.
set -o pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")" # Assumes script is in a 'scripts' subdirectory
WORKSPACE_DIR="${REPO_ROOT}/docs/architecture/structurizr"
PLANTUML_OUTPUT_DIR="${WORKSPACE_DIR}/plantuml"
SVG_OUTPUT_DIR="${WORKSPACE_DIR}/svg"
STRUCTURIZR_CONTAINER_NAME="structurizr-export-temp"

# --- Main Script ---
echo "Starting Structurizr diagram generation process..."

# Create output directories if they don't exist
echo "Creating output directories..."
mkdir -p "${PLANTUML_OUTPUT_DIR}"
mkdir -p "${SVG_OUTPUT_DIR}"
echo "Output directories ensured: ${PLANTUML_OUTPUT_DIR} and ${SVG_OUTPUT_DIR}"

# Check if Docker is running
echo "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker does not seem to be running. Please start Docker and try again."
    exit 1
fi
echo "Docker is running."

# Function to cleanup Structurizr container
cleanup_structurizr_container() {
    echo "Cleaning up Structurizr container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${STRUCTURIZR_CONTAINER_NAME}$"; then
        echo "Stopping container ${STRUCTURIZR_CONTAINER_NAME}..."
        docker stop "${STRUCTURIZR_CONTAINER_NAME}" || echo "Warning: Failed to stop container ${STRUCTURIZR_CONTAINER_NAME}. It might have already stopped."
        echo "Removing container ${STRUCTURIZR_CONTAINER_NAME}..."
        docker rm "${STRUCTURIZR_CONTAINER_NAME}" || echo "Warning: Failed to remove container ${STRUCTURIZR_CONTAINER_NAME}. It might have already been removed."
    else
        echo "Container ${STRUCTURIZR_CONTAINER_NAME} not found, no cleanup needed."
    fi
}

# Ensure cleanup on script exit or interruption
trap cleanup_structurizr_container EXIT SIGINT SIGTERM

# Start the Structurizr Lite Docker container
echo "Starting Structurizr Lite container (${STRUCTURIZR_CONTAINER_NAME})..."
docker run -d --name "${STRUCTURIZR_CONTAINER_NAME}" \
    -v "${WORKSPACE_DIR}":/usr/local/structurizr \
    structurizr/lite
echo "Container started."

# Wait for the container to initialize
echo "Waiting for container to initialize (10 seconds)..."
sleep 10

# Export diagrams to PlantUML format
echo "Exporting diagrams to PlantUML format..."
if docker exec "${STRUCTURIZR_CONTAINER_NAME}" export -workspace /usr/local/structurizr/workspace.dsl -format plantuml -output /usr/local/structurizr/plantuml; then
    echo "PlantUML export successful."
else
    echo "Error: PlantUML export failed. Check container logs for details:"
    docker logs "${STRUCTURIZR_CONTAINER_NAME}"
    exit 1 # Exit here because stopping/removing a non-existent or problematic container might hide useful logs
fi

# Stop and remove the Structurizr container (handled by trap)
# cleanup_structurizr_container will be called automatically on exit

# Convert PlantUML files to SVG
echo "Converting PlantUML files to SVG..."
# Check if any .puml files exist before attempting conversion
if compgen -G "${PLANTUML_OUTPUT_DIR}/*.puml" > /dev/null; then
    echo "Found PlantUML files in ${PLANTUML_OUTPUT_DIR}. Proceeding with SVG conversion."
    # Using plantuml/plantuml-server as it's a common image for this.
    # Mount PlantUML output dir as /data (read-only) and SVG output dir as /output (read-write)
    if docker run --rm \
        -v "${PLANTUML_OUTPUT_DIR}":/data:ro \
        -v "${SVG_OUTPUT_DIR}":/output \
        plantuml/plantuml-server -verbose -o /output /data/*.puml; then
        echo "SVG conversion successful."
    else
        echo "Error: SVG conversion failed. Check for errors from the PlantUML container."
        # Note: plantuml/plantuml-server might not produce detailed logs on stdout for conversion errors.
        # Users might need to check the generated files or PlantUML syntax.
        exit 1
    fi
else
    echo "No PlantUML files (.puml) found in ${PLANTUML_OUTPUT_DIR}. Skipping SVG conversion."
    # This might be an error condition depending on expectations, but the script will not fail here.
    # If workspace.dsl is empty or has no views, no .puml files will be generated.
fi


echo "------------------------------------------------------------"
echo "Diagram generation process completed!"
echo "PlantUML files are in: ${PLANTUML_OUTPUT_DIR}"
echo "SVG files are in: ${SVG_OUTPUT_DIR}"
echo "------------------------------------------------------------"

exit 0
