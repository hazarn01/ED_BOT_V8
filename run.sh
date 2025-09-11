#!/bin/bash

# Simple bash script to run Makefile.v8 targets without make

set -e

TARGET=${1:-help}

case "$TARGET" in
    bootstrap)
        echo "🔧 Setting up Python virtual environment and installing dependencies..."
        python3 -m venv .venv && source .venv/bin/activate && pip install -U pip wheel && \
        pip install -r requirements.v8.txt || true
        ;;
    
    up)
        echo "🚀 Starting Docker stack..."
        docker compose -f docker-compose.v8.yml up -d --build
        ;;
    
    up-cpu)
        echo "🚀 Starting Docker stack with CPU/Ollama profile..."
        docker compose -f docker-compose.v8.yml --profile cpu up -d --build ollama ollama-pull api worker
        ;;
    
    down)
        echo "🛑 Stopping Docker stack..."
        docker compose -f docker-compose.v8.yml down
        ;;
    
    seed)
        echo "🌱 Seeding database with sample medical data..."
        source .venv/bin/activate && PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 scripts/seed_documents.py
        ;;
    
    health)
        echo "🏥 Checking API health..."
        curl -f http://localhost:8001/health || echo "API not responding"
        ;;
    
    dev-setup)
        echo "🎯 Running complete development setup..."
        $0 bootstrap
        $0 seed  
        $0 up-cpu
        echo "✅ Development setup complete!"
        ;;
    
    logs)
        echo "📜 Showing Docker logs..."
        docker compose -f docker-compose.v8.yml logs -f --tail=200
        ;;
    
    test)
        echo "🧪 Running tests..."
        python scripts/run_tests.py
        ;;
    
    query-test)
        echo "🔍 Testing sample queries..."
        source .venv/bin/activate && PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 scripts/test_queries.py
        ;;
    
    help|*)
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Commands:"
        echo "  bootstrap    - Setup Python venv and install dependencies"
        echo "  up          - Start Docker stack"
        echo "  up-cpu      - Start Docker stack with CPU/Ollama profile"
        echo "  down        - Stop Docker stack"
        echo "  seed        - Seed database with sample data"
        echo "  health      - Check API health"
        echo "  dev-setup   - Complete development setup (bootstrap + seed + up-cpu)"
        echo "  logs        - Show Docker logs"
        echo "  test        - Run tests"
        echo "  query-test  - Test sample queries"
        echo "  help        - Show this help message"
        ;;
esac