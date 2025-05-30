#!/bin/sh

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Setup tasks
log "Running setup tasks..."

# Create proxy network if it doesn't exist
if ! docker network ls | grep -q "proxy"; then
    log "Creating Docker network 'proxy'..."
    docker network create proxy || log "Network might already exist or insufficient permissions"
fi

# Create and set permissions for acme.json if it doesn't exist
if [ ! -f "acme.json" ]; then
    log "Creating acme.json..."
    touch acme.json
    chmod 600 acme.json
    log "acme.json created with proper permissions"
fi

# Clean up any problematic database files if they exist
log "Checking for problematic database files..."
if [ -d "database" ] && [ -e "database/#innodb_redo" ]; then
    log "Found problematic database files. Adjusting permissions..."
    chmod -R 755 database || log "Failed to change permissions. You might need to use sudo."
fi

# Stop and remove existing containers if requested
if [ "$1" = "clean" ]; then
    log "Stopping existing containers and removing volumes..."
    docker compose down -v
fi

# Start the application
log "Starting the application..."
docker compose up --build -d

log "Service started successfully!"