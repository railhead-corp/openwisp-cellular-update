#!/bin/bash

# OpenWISP Server - Docker Stop Script
# This script stops and removes all running containers

set -e  # Exit on error

echo "======================================"
echo "Stopping all containers..."
echo "======================================"

# Stop all running containers
docker compose down

echo ""
echo "======================================"
echo "All containers stopped successfully!"
echo "======================================"
echo ""
echo "To start containers again:"
echo "  ./docker-start.sh"
echo ""
echo "To remove all data (volumes):"
echo "  docker compose down -v"
echo ""
