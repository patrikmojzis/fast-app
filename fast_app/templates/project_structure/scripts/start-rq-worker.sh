#!/bin/bash

# Default values
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
ENV=${ENV:-debug}
QUEUE_NAME=${RQ_QUEUE_NAME:-default}

# Redis database used for background queue
REDIS_DB=0

# Construct Redis URL
REDIS_URL="redis://${REDIS_HOST}:6379/${REDIS_DB}"

echo "Starting RQ Worker with scheduler..."
echo "Environment: $ENV"
echo "Redis URL: $REDIS_URL"
echo "Queue: $QUEUE_NAME"

# Start RQ worker with scheduler
exec rq worker $QUEUE_NAME --with-scheduler --url $REDIS_URL