#!/bin/bash
# Fix storage directory permissions for Docker deployment
# Ensures the mounted directory is writable by the container user (UID 999 by default)

STORAGE_DIR="./storage"
CONTAINER_UID=999
CONTAINER_GID=999

# Create directory if missing
mkdir -p "$STORAGE_DIR"

# Set correct ownership and minimal needed permissions
sudo chown -R $CONTAINER_UID:$CONTAINER_GID "$STORAGE_DIR"

# 755 = owner (Docker user) can write, others can only read/execute (browse)
find "$STORAGE_DIR" -type d -exec chmod 755 {} \;
find "$STORAGE_DIR" -type f -exec chmod 644 {} \;

echo "✅ Storage directory ready with UID:GID $CONTAINER_UID:$CONTAINER_GID"
ls -la "$STORAGE_DIR"