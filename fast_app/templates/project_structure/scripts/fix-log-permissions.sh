#!/bin/bash

# Fix log directory permissions for Docker deployment
# This ensures the mounted log directory is writable by the container user

LOG_DIR="./log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Set permissions to be writable by any user (Docker containers often have different UIDs)
chmod 777 "$LOG_DIR"
touch "$LOG_DIR/app.log"
chmod 666 "$LOG_DIR/app.log"  # if the file exists 

echo "Log directory permissions fixed: $LOG_DIR"
ls -la "$LOG_DIR"