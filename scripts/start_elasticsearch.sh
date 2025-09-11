#!/bin/bash
"""
Start Elasticsearch service for hybrid search testing.
This script ensures Elasticsearch is running and properly configured.
"""

set -e

echo "🚀 Starting Elasticsearch for hybrid search..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not available. Please install Docker Desktop and enable WSL integration."
    echo "Visit: https://docs.docker.com/desktop/wsl/"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available."
    exit 1
fi

# Determine which compose command to use
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "📦 Using Docker Compose: $COMPOSE_CMD"

# Start Elasticsearch with search profile
echo "🔄 Starting Elasticsearch service..."
$COMPOSE_CMD -f docker-compose.v8.yml --profile search up -d elasticsearch

# Wait for Elasticsearch to be ready
echo "⏳ Waiting for Elasticsearch to be ready..."
MAX_TRIES=30
COUNTER=0

while [ $COUNTER -lt $MAX_TRIES ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:9200/_cluster/health | grep -q "200"; then
        echo "✅ Elasticsearch is ready!"
        break
    fi
    
    COUNTER=$((COUNTER + 1))
    echo "  Attempt $COUNTER/$MAX_TRIES..."
    sleep 2
done

if [ $COUNTER -eq $MAX_TRIES ]; then
    echo "❌ Elasticsearch failed to start within 60 seconds"
    echo "Check logs with: docker compose -f docker-compose.v8.yml logs elasticsearch"
    exit 1
fi

# Show cluster health
echo ""
echo "🏥 Elasticsearch Cluster Health:"
curl -s http://localhost:9200/_cluster/health | python3 -m json.tool

# Create indices using our management script
echo ""
echo "📚 Creating Elasticsearch indices..."
python3 scripts/es_management.py create-indices

echo ""
echo "✅ Elasticsearch is ready for hybrid search!"
echo ""
echo "Commands:"
echo "  make es-health      - Check cluster health"
echo "  make es-indices     - List indices"
echo "  make es-stats       - Show index statistics"
echo "  make es-backfill    - Backfill existing documents (dry run)"