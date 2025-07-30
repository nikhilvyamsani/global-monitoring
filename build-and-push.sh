#!/bin/bash

set -e

echo "🚀 Building and pushing multi-architecture Docker images..."

# Create buildx builder if it doesn't exist
docker buildx create --name multiarch --use --bootstrap 2>/dev/null || docker buildx use multiarch

# Build and push client image
echo "📦 Building client image..."
cd client-docker
docker buildx build \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --no-cache \
    --tag nikhilvyamsani/metrics-client:latest \
    --push .

echo "✅ Client image pushed successfully"

# Build and push server image
echo "📦 Building server image..."
cd ../server-docker
docker buildx build \
    --no-cache \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --tag nikhilvyamsani/metrics-server:latest \
    --push .

echo "✅ Server image pushed successfully"
echo "🎉 All images built and pushed to Docker Hub!"
