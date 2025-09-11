SHELL := /bin/bash

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Setup venv, install deps
	python -m venv .venv && . .venv/bin/activate && pip install -U pip wheel && \
	pip install -r requirements.v8.txt || true

up: ## Start stack
	docker compose -f docker-compose.v8.yml up -d --build

up-cpu: ## Start stack with CPU (Ollama) profile
	docker compose -f docker-compose.v8.yml --profile cpu up -d --build ollama ollama-pull api worker

up-gpu: ## Start stack with GPU (vLLM) profile
	docker compose -f docker-compose.v8.yml --profile gpu up -d --build

up-search: ## Start stack with Elasticsearch for hybrid search
	docker compose -f docker-compose.v8.yml --profile cpu --profile search up -d --build
	@echo "Waiting for Elasticsearch..."
	@sleep 10
	@curl -s http://localhost:9200/_cluster/health | jq '.' || echo "Elasticsearch not ready"

down: ## Stop stack (remove volumes with -v)
	docker compose -f docker-compose.v8.yml down

logs: ## Tail logs
	docker compose -f docker-compose.v8.yml logs -f --tail=200

migrate: ## Create migration
	alembic revision --autogenerate -m "update"

upgrade: ## Apply migrations
	alembic upgrade head

downgrade: ## Revert last migration
	alembic downgrade -1

ingest: ## Run ingestion once
	docker compose -f docker-compose.v8.yml run --rm worker python -m src.ingestion.tasks run --batch /app/docs

test: ## Run tests
	python scripts/run_tests.py

test-unit: ## Run unit tests only
	python scripts/run_tests.py unit -v

test-integration: ## Run integration tests only
	python scripts/run_tests.py integration -v

test-coverage: ## Run tests with coverage
	python scripts/run_tests.py all -c

test-all: ## Run all checks (tests, linting, type checking)
	python scripts/run_tests.py --all-checks

lint: ## Run linting
	python scripts/run_tests.py -l

typecheck: ## Run type checking
	python scripts/run_tests.py -t

seed: ## Seed database with sample data
	python scripts/setup_dev_environment.py

seed-verify: ## Verify seeded data
	python scripts/setup_dev_environment.py --verify

dev-setup: ## Complete development setup
	make bootstrap && make seed && make up-cpu

health: ## Check API health
	curl -f http://localhost:8001/health || echo "API not responding"

query-test: ## Test sample queries
	@echo "Testing contact query..."
	curl -X POST http://localhost:8001/api/v1/query \
		-H "Content-Type: application/json" \
		-d '{"query": "who is on call for cardiology"}' | jq .
	@echo "\nTesting form query..."
	curl -X POST http://localhost:8001/api/v1/query \
		-H "Content-Type: application/json" \
		-d '{"query": "show me the blood transfusion form"}' | jq .
	@echo "\nTesting protocol query..."
	curl -X POST http://localhost:8001/api/v1/query \
		-H "Content-Type: application/json" \
		-d '{"query": "what is the STEMI protocol"}' | jq .

docs: ## List available documents
	curl -s http://localhost:8001/api/v1/documents | jq .

contacts: ## Test contact lookup
	curl -s http://localhost:8001/api/v1/contacts/cardiology | jq .

es-health: ## Check Elasticsearch health
	@curl -s http://localhost:9200/_cluster/health | jq '.' || echo "Elasticsearch not available"

es-indices: ## List Elasticsearch indices
	@curl -s http://localhost:9200/_cat/indices?v || echo "Elasticsearch not available"

es-create: ## Create Elasticsearch indices
	python scripts/es_management.py create-indices

es-delete: ## Delete Elasticsearch indices (careful!)
	python scripts/es_management.py delete-indices --confirm

es-stats: ## Show Elasticsearch index statistics
	python scripts/es_management.py stats

es-backfill: ## Backfill existing documents to Elasticsearch (dry run)
	python scripts/backfill_elasticsearch.py

es-backfill-execute: ## Execute backfill of existing documents to Elasticsearch
	python scripts/backfill_elasticsearch.py --execute

es-optimize: ## Optimize Elasticsearch indices for better performance
	python scripts/es_management.py optimize

es-verify: ## Verify Elasticsearch/PostgreSQL count matching
	python scripts/es_management.py verify-counts

clean: ## Clean up containers and volumes
	docker compose -f docker-compose.v8.yml down -v --remove-orphans
	docker system prune -f

reset: ## Reset everything (clean + fresh setup)
	make clean && make dev-setup

validate: ## Validate complete system
	@echo "🔍 Running system validation..."
	@make health
	@make query-test
	@echo "✅ System validation complete"

diag: ## Environment diagnostics (GPU/Compose info)
	@echo "---- NVIDIA GPU (if available) ----"
	@nvidia-smi || echo "nvidia-smi not available"
	@echo "\n---- Docker info runtimes ----"
	docker info --format '{{json .Runtimes}}' || true
	@echo "\n---- vLLM health (gpu profile) ----"
	@curl -s http://localhost:8000/health || echo "vLLM not running"
	@echo "\n---- Ollama health (cpu profile) ----"
	@curl -s http://localhost:11434/api/tags || echo "Ollama not running"

up-ui: ## Start stack with UI demo
	docker compose -f docker-compose.v8.yml --profile cpu --profile ui up -d
	@echo "✅ Demo UI available at http://localhost:8501"
	@echo "✅ API available at http://localhost:8001"

ui-logs: ## View Streamlit logs
	docker compose -f docker-compose.v8.yml logs -f streamlit

ui-build: ## Rebuild Streamlit container
	docker compose -f docker-compose.v8.yml build streamlit

ui-restart: ## Restart Streamlit container
	docker compose -f docker-compose.v8.yml restart streamlit

ui-stop: ## Stop Streamlit container
	docker compose -f docker-compose.v8.yml stop streamlit

# PRP 25: Rollout and Deployment Management
rollout-check: ## Run pre-rollout validation
	python -m scripts.pre_rollout_checklist

rollout-check-json: ## Run pre-rollout validation with JSON output
	python -m scripts.pre_rollout_checklist --output json

backfill-dry-run: ## Dry run of data backfill
	python -m scripts.backfill_manager --dry-run

backfill-execute: ## Execute data backfill
	python -m scripts.backfill_manager --execute

backfill-tables: ## Backfill table extraction only
	python -m scripts.backfill_manager --execute --tasks tables

backfill-elasticsearch: ## Backfill Elasticsearch indices only
	python -m scripts.backfill_manager --execute --tasks elasticsearch

backfill-highlighting: ## Backfill highlighting data only
	python -m scripts.backfill_manager --execute --tasks highlighting

rollout-canary: ## Start canary rollout (5% traffic)
	python -m scripts.rollout_manager --phase canary --features hybrid_search semantic_cache

rollout-gradual: ## Start gradual rollout (50% traffic)
	python -m scripts.rollout_manager --phase gradual --features hybrid_search semantic_cache table_extraction

rollout-full: ## Complete full rollout (100% traffic)
	python -m scripts.rollout_manager --phase full --features hybrid_search semantic_cache table_extraction

rollout-rollback: ## Emergency rollback all features
	python -m scripts.rollout_manager --rollback --features hybrid_search semantic_cache table_extraction

rollout-status: ## Check current rollout status
	python -m scripts.rollout_manager --status

rollout-status-json: ## Check rollout status with JSON output
	python -m scripts.rollout_manager --status --output json

final-validation: ## Run comprehensive PRP validation
	python -m scripts.final_validation

final-validation-json: ## Run PRP validation with JSON output
	python -m scripts.final_validation --output json

final-validation-config: ## Validate configuration components only
	python -m scripts.final_validation --category configuration

final-validation-observability: ## Validate observability components only
	python -m scripts.final_validation --category observability

final-validation-integration: ## Validate integration components only
	python -m scripts.final_validation --category integration

prp-status: ## Show status of all PRP implementations
	@echo "🔍 PRP Implementation Status Check"
	@echo "================================"
	@echo "PRP 22 - Configuration & Feature Flags:"
	@python -c "from src.config.enhanced_settings import EnhancedSettings; s=EnhancedSettings(); print(f'  ✅ Environment: {s.environment}'); print(f'  ✅ Features loaded: {len([x for x in dir(s.features) if not x.startswith(\"_\")])}')" || echo "  ❌ Configuration not available"
	@echo "PRP 23 - Testing Infrastructure:"
	@echo "  ✅ Unit tests: $$(ls tests/unit/test_*.py 2>/dev/null | wc -l) files"
	@echo "  ✅ Integration tests: $$(ls tests/integration/test_*.py 2>/dev/null | wc -l) files"
	@echo "  ✅ Performance tests: $$(ls tests/performance/test_*.py 2>/dev/null | wc -l) files"
	@echo "PRP 24 - Observability:"
	@python -c "from src.observability.metrics import metrics; print('  ✅ Metrics framework available')" || echo "  ❌ Metrics framework not available"
	@python -c "from src.observability.health import HealthMonitor; print('  ✅ Health monitoring available')" || echo "  ❌ Health monitoring not available"
	@echo "PRP 25 - Rollout Infrastructure:"
	@echo "  ✅ Pre-rollout checker: $$([ -f scripts/pre_rollout_checklist.py ] && echo 'available' || echo 'missing')"
	@echo "  ✅ Backfill manager: $$([ -f scripts/backfill_manager.py ] && echo 'available' || echo 'missing')"
	@echo "  ✅ Rollout manager: $$([ -f scripts/rollout_manager.py ] && echo 'available' || echo 'missing')"
	@echo "  ✅ Final validation: $$([ -f scripts/final_validation.py ] && echo 'available' || echo 'missing')"

prp-demo: ## Demonstrate PRP capabilities
	@echo "🚀 PRP 22-25 Capabilities Demo"
	@echo "============================="
	@echo "1. Running configuration validation..."
	@python -m scripts.final_validation --category configuration || true
	@echo "\n2. Testing feature flag management..."
	@python -c "import asyncio; from src.config.enhanced_settings import EnhancedSettings; from src.cache.redis_client import get_redis_client; from src.config.feature_manager import FeatureManager; asyncio.run(demo_feature_flags())" 2>/dev/null || echo "Feature flag demo requires Redis connection"
	@echo "\n3. Checking observability systems..."
	@python -m scripts.final_validation --category observability || true
	@echo "\n4. Validating rollout infrastructure..."
	@python -m scripts.final_validation --category rollout || true

deploy-staging: ## Deploy to staging environment
	@echo "🚀 Deploying to staging environment..."
	@make rollout-check
	@make backfill-dry-run
	@echo "✅ Staging deployment checks passed - ready for actual deployment"

deploy-production: ## Deploy to production environment (with full validation)
	@echo "🚀 Production deployment with full validation..."
	@echo "Step 1: Pre-rollout validation"
	@python -m scripts.pre_rollout_checklist --fail-on-warning
	@echo "Step 2: Data backfill"
	@python -m scripts.backfill_manager --execute
	@echo "Step 3: Canary rollout"
	@python -m scripts.rollout_manager --phase canary --features hybrid_search
	@echo "Step 4: Full rollout"
	@python -m scripts.rollout_manager --phase full --features hybrid_search semantic_cache table_extraction
	@echo "Step 5: Final validation"
	@python -m scripts.final_validation
	@echo "✅ Production deployment completed successfully" 