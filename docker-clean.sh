#!/bin/bash

echo "Docker Cleanup Script"
echo "===================="

# Check if Docker is running
if ! docker info &>/dev/null; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Define the project name (used to identify containers)
PROJECT_NAME="website-backend"

# Function to display help
show_help() {
    echo "Usage: ./docker-clean.sh [OPTION]"
    echo
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  -s, --stop      Stop running containers without removing them"
    echo "  -c, --clean     Remove containers and networks (default)"
    echo "  -a, --all       Remove everything including volumes (data will be lost)"
    echo "  -p, --prune     Prune unused Docker resources system-wide"
    echo
}

# Parse command line arguments
OPTION="clean"  # Default option
if [ $# -gt 0 ]; then
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--stop)
            OPTION="stop"
            ;;
        -c|--clean)
            OPTION="clean"
            ;;
        -a|--all)
            OPTION="all"
            ;;
        -p|--prune)
            OPTION="prune"
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
fi

# Stop containers
if [ "$OPTION" = "stop" ] || [ "$OPTION" = "clean" ] || [ "$OPTION" = "all" ]; then
    echo "Stopping containers..."
    docker-compose down
fi

# Remove containers and networks
if [ "$OPTION" = "clean" ] || [ "$OPTION" = "all" ]; then
    echo "Removing containers and networks..."
    docker-compose down --remove-orphans
fi

# Remove volumes (data)
if [ "$OPTION" = "all" ]; then
    echo "Removing volumes (DATA WILL BE LOST)..."
    docker-compose down --volumes
    echo "Removing all related images..."
    # Get image IDs used in the docker-compose file
    IMAGE_IDS=$(docker-compose config | grep image: | awk '{print $2}')
    for IMAGE_ID in $IMAGE_IDS; do
        docker rmi $IMAGE_ID
    done
fi

# Prune unused Docker resources
if [ "$OPTION" = "prune" ]; then
    echo "Pruning unused Docker resources..."
    docker system prune -f
    echo "Pruning unused volumes..."
    docker volume prune -f
fi

echo "Cleanup completed."
