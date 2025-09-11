#!/bin/bash
# Setup script for Elasticsearch in Docker
# This script should be run from a system with Docker installed

set -e

echo "🚀 Setting up Elasticsearch for ED Bot v8"
echo ""
echo "Prerequisites:"
echo "  - Docker Desktop installed and running"
echo "  - WSL integration enabled in Docker Desktop settings"
echo ""

# Check Docker availability
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not available!"
    echo ""
    echo "To install Docker Desktop:"
    echo "  1. Download Docker Desktop from https://www.docker.com/products/docker-desktop"
    echo "  2. Install and start Docker Desktop"
    echo "  3. Enable WSL 2 integration in Docker Desktop settings"
    echo "  4. Restart WSL and run this script again"
    exit 1
fi

echo "✅ Docker is available"

# Check Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose not found"
    exit 1
fi

echo "✅ Docker Compose is available: $COMPOSE_CMD"

# Start Elasticsearch using docker-compose
echo ""
echo "🔄 Starting Elasticsearch service..."
cd /mnt/d/Dev/EDbotv8

# Start only Elasticsearch with the search profile
$COMPOSE_CMD -f docker-compose.v8.yml --profile search up -d elasticsearch

# Wait for Elasticsearch to be ready
echo "⏳ Waiting for Elasticsearch to be ready..."
MAX_TRIES=30
COUNTER=0

while [ $COUNTER -lt $MAX_TRIES ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:9200/_cluster/health 2>/dev/null | grep -q "200"; then
        echo "✅ Elasticsearch is ready!"
        break
    fi
    
    COUNTER=$((COUNTER + 1))
    echo "  Attempt $COUNTER/$MAX_TRIES..."
    sleep 2
done

if [ $COUNTER -eq $MAX_TRIES ]; then
    echo "❌ Elasticsearch failed to start"
    echo "Check logs with: $COMPOSE_CMD -f docker-compose.v8.yml logs elasticsearch"
    exit 1
fi

# Show cluster health
echo ""
echo "🏥 Elasticsearch Cluster Health:"
curl -s http://localhost:9200/_cluster/health | python3 -m json.tool

# Create indices
echo ""
echo "📚 Creating Elasticsearch indices..."
python3 scripts/es_management.py create-indices

# Show index statistics
echo ""
python3 scripts/es_management.py stats

echo ""
echo "✅ Elasticsearch is ready for dual indexing!"
echo ""
echo "Next steps:"
echo "  1. Run integration tests: python3 -m pytest tests/integration/test_dual_indexing.py -v"
echo "  2. Backfill existing documents: make es-backfill-execute"
echo "  3. Start ingestion with dual indexing: make ingest"