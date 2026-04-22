#!/bin/bash

# OpenWISP Server - Docker Build and Start Script
# This script builds the Docker image with latest changes and starts all containers

set -e  # Exit on error

echo "======================================"
echo "Building Docker image with latest changes..."
echo "======================================"

# Build the web service image
docker compose build web

echo ""
echo "======================================"
echo "Starting all containers..."
echo "======================================"

# Start all services in detached mode
docker compose up -d

echo ""
echo "======================================"
echo "Waiting for services to be ready..."
echo "======================================"

# Wait a few seconds for services to initialize
sleep 5

echo ""
echo "======================================"
echo "Checking container status..."
echo "======================================"

# Show running containers
docker compose ps

echo ""
echo "======================================"
echo "OpenWISP Server is now running!"
echo "======================================"
echo ""
echo "Access URLs:"
echo "  - Web Interface: http://localhost:8000"
echo "  - Admin Panel:   http://localhost:8000/admin/"
echo ""
echo "View logs:"
echo "  docker compose logs -f web"
echo ""
echo "Stop containers:"
echo "  ./docker-stop.sh"
echo ""
