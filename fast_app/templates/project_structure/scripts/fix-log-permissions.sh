#!/bin/bash
# Fix log directory permissions for Docker deployment
# Ensures the mounted log directory is writable by the container user (UID 999 by default)

LOG_DIR="./log"
CONTAINER_UID=999
CONTAINER_GID=999

# Create directory and file if they don’t exist
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/app.log"

# Set correct ownership and minimal needed permissions
sudo chown -R $CONTAINER_UID:$CONTAINER_GID "$LOG_DIR"
chmod 755 "$LOG_DIR"
chmod 644 "$LOG_DIR/app.log"

echo "✅ Log directory ready with UID:GID $CONTAINER_UID:$CONTAINER_GID"
ls -la "$LOG_DIR"