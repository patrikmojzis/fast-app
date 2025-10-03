#!/bin/bash

# Fix log directory permissions for Docker deployment
# This ensures the mounted log directory is writable by the container user

LOG_DIR="/log"

# Resolve default log file name from env (defaults to app.log)
LOG_FILE_NAME="${LOG_FILE_NAME:-app.log}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Set permissions to be writable by any user (Docker containers often have different UIDs)
chmod 777 "$LOG_DIR"

# Ensure default log file exists and set permissions
touch "$LOG_DIR/$LOG_FILE_NAME"

# Set 666 on all .log files in the log directory
chmod 666 "$LOG_DIR"/*.log 2>/dev/null || true

echo "Log directory permissions fixed: $LOG_DIR"
ls -la "$LOG_DIR"