#!/bin/bash
# Wait for Docker Desktop to fully start

echo "⏳ Waiting for Docker Desktop to fully start..."
echo ""

max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    
    if docker info >/dev/null 2>&1; then
        echo ""
        echo "✓ Docker Desktop is running!"
        echo ""
        docker --version
        echo ""
        docker info | grep "Server Version" || true
        echo ""
        echo "Ready to start AGORA infrastructure."
        exit 0
    fi
    
    if [ $((attempt % 5)) -eq 0 ]; then
        echo "Still waiting... ($attempt/$max_attempts seconds)"
    fi
    
    sleep 1
done

echo ""
echo "❌ Docker Desktop did not start within $max_attempts seconds"
echo ""
echo "Please ensure Docker Desktop is running:"
echo "1. Look for Docker icon in menu bar"
echo "2. Click icon and verify 'Docker Desktop is running'"
echo "3. If not running, launch from Applications/Docker.app"
echo ""
exit 1
