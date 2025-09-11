# ED Bot v8 - Emergency Department Medical AI Assistant

A HIPAA-compliant medical RAG system using local LLMs, structured extraction, and query classification for emergency department workflows.

## 🏥 Overview

ED Bot v8 is a complete ground-up rebuild designed for reproducibility, medical safety, and HIPAA compliance. The system provides:

- **6-Type Query Classification**: CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY
- **Local LLM Inference**: GPT-OSS 20B via vLLM for complete data privacy
- **Structured Document Processing**: Unstructured + LangExtract for medical content
- **Safety Validation**: Medical term validation and dosage safety checks
- **PDF Form Serving**: Direct PDF retrieval with authentication
- **On-call Contact Integration**: Mock Amion service for physician lookup

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Make

### Development Setup

```bash
# Clone and setup
git clone <repository>
cd EDbotv8

# Complete development setup
make dev-setup

# Verify deployment
make validate
```

### Manual Setup

```bash
# 1. Setup Python environment
make bootstrap

# 2. Seed database with sample data
make seed

# 3. Start all services
make up

# 4. Test the system
make query-test
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  Query          │    │  LLM            │
│   Endpoints     │───▶│  Processor      │───▶│  GPT-OSS 20B    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │  Redis          │    │  Document       │
│   PostgreSQL    │    │  Cache          │    │  Processing     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

- **API Layer**: FastAPI with async endpoints, PDF serving, HIPAA logging
- **Query Processing**: Classification → Routing → Response with validation
- **LLM Integration**: Local GPT-OSS 20B (primary) with Azure fallback
- **Data Layer**: PostgreSQL with pgvector, Redis caching
- **Document Processing**: Unstructured PDF parsing + LangExtract entities
- **Safety Systems**: Medical validation, PHI scrubbing, audit trails

## 📋 Query Types

### 1. CONTACT - On-call Physician Lookup
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "who is on call for cardiology"}'
```

### 2. FORM - Direct PDF Retrieval
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me the blood transfusion form"}'
```

### 3. PROTOCOL - Clinical Protocols
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the STEMI protocol"}'
```

### 4. CRITERIA - Clinical Decision Rules
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Ottawa ankle rules"}'
```

### 5. DOSAGE - Medication Dosing
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "epinephrine dosage for cardiac arrest"}'
```

### 6. SUMMARY - Multi-source Synthesis
```bash
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "summarize chest pain workup"}'
```

## 🛠️ Development

### Available Commands

```bash
# Development
make dev-setup      # Complete setup (bootstrap + seed + up)
make bootstrap      # Setup Python environment
make up             # Start services
make down           # Stop services
make logs           # View logs

# Database
make migrate        # Create migration
make upgrade        # Apply migrations
make seed           # Seed with sample data
make seed-verify    # Verify seeded data

# Testing
make test           # Run all tests
make test-unit      # Unit tests only
make test-integration # Integration tests only
make test-coverage  # Tests with coverage
make test-all       # All checks (tests + linting + types)
make lint           # Code linting
make typecheck      # Type checking

# Validation
make health         # Check API health
make query-test     # Test sample queries
make docs           # List documents
make contacts       # Test contact lookup
make validate       # Complete system validation

# Maintenance
make clean          # Clean containers/volumes
make reset          # Reset everything (clean + dev-setup)
```

### Project Structure

```
src/
  api/                    # FastAPI application
    app.py               # Main application setup
    endpoints.py         # API route handlers  
    dependencies.py      # Dependency injection
  
  ai/                    # LLM clients and prompts
    gpt_oss_client.py   # Local GPT-OSS 20B client
    azure_fallback.py   # Azure OpenAI fallback
    prompts.py          # Medical prompt templates
  
  pipeline/              # Query processing pipeline
    classifier.py       # 6-type query classification
    router.py          # Query routing logic
    query_processor.py  # Main processing orchestration
  
  models/               # Data models
    entities.py         # SQLAlchemy ORM models
    schemas.py          # Pydantic validation schemas
    query_types.py      # QueryType enum definition
  
  services/             # External services
    contact_service.py  # Amion integration (mock)
  
  validation/           # Safety and compliance
    medical_validator.py # Medical safety checks
    hipaa.py            # PHI scrubbing

tests/
  unit/                 # Unit tests
  integration/          # Integration tests
  conftest.py          # Test configuration

scripts/
  seed_documents.py     # Database seeding
  setup_dev_environment.py # Complete environment setup
  run_tests.py         # Test runner
  validate_deployment.py # Deployment validation
```

## 🔒 Security & Compliance

### HIPAA Compliance
- ✅ Local LLM inference only (no external API calls)
- ✅ PHI scrubbing in logs (`LOG_SCRUB_PHI=true`)
- ✅ Audit trails for all medical queries
- ✅ Secure PDF serving with authentication
- ✅ No PHI in cached responses

### Medical Safety
- ✅ Never guess medical information - only verified protocols
- ✅ Always preserve source citations
- ✅ Validate dosages against known safe ranges
- ✅ Include confidence scores and warnings
- ✅ Flag low-confidence answers

### Performance Requirements
- ✅ Response time: <1.5s for non-LLM queries
- ✅ Classification accuracy: >90% target
- ✅ Citation preservation: 100% requirement
- ✅ PDF availability: Always return actual files

## 🧪 Testing

### Primary Test Queries
These queries must always pass:

```bash
# Protocol with timing and contacts
"what is the ED STEMI protocol"

# Form returning actual PDF
"show me the blood transfusion form"

# Contact with current on-call
"who is on call for cardiology"
```

### Test Execution

```bash
# Run all tests with coverage
make test-coverage

# Run specific test types
make test-unit
make test-integration

# Run validation on deployed system
make validate

# Manual API testing
make query-test
```

## 🐳 Docker Services

- **API**: FastAPI application (port 8001)
- **LLM**: vLLM serving GPT-OSS 20B (port 8000) 
- **Database**: PostgreSQL with pgvector
- **Cache**: Redis for query caching
- **Worker**: Document processing worker

## 📝 Configuration

Key environment variables:

```bash
# LLM Backend
LLM_BACKEND=gpt-oss
VLLM_BASE_URL=http://llm:8000
GPT_OSS_MODEL=openai/gpt-oss-20b

# HIPAA Compliance  
LOG_SCRUB_PHI=true
DISABLE_EXTERNAL_CALLS=true

# Performance
CACHE_TTL_SECONDS=300
MAX_WORKERS=4
```

## 🚦 Status

**Current Phase**: ✅ **Complete Implementation**

All major components implemented:
- ✅ Query classification (6 types)
- ✅ Database models and migrations  
- ✅ LLM client integration
- ✅ Medical validation and safety
- ✅ FastAPI endpoints and PDF serving
- ✅ Query processing pipeline
- ✅ Contact service (mock Amion)
- ✅ Document registry and seeding
- ✅ Comprehensive test suite
- ✅ Deployment validation

### Key Features Delivered

1. **Medical Safety First**: Never guess medical info, always validate
2. **HIPAA Compliant**: Local inference, PHI scrubbing, audit trails
3. **Production Ready**: Comprehensive testing, error handling, monitoring
4. **Reproducible**: Complete containerization with sample data
5. **Extensible**: Clean architecture for future enhancements

## 📊 Validation Report

The system includes comprehensive validation:

```bash
# Run complete system validation
make validate

# Check validation report
cat validation_report.json
```

Validates:
- API health and availability
- All query types processing correctly
- Response timing requirements
- Error handling
- Document retrieval
- Contact lookup functionality

## 🤝 Contributing

1. Follow medical safety guidelines in `CLAUDE.md`
2. Write tests for new features
3. Maintain HIPAA compliance
4. Preserve citation requirements
5. Update documentation

## 📄 License

This project is intended for educational and healthcare purposes. Ensure compliance with local healthcare regulations and data privacy laws.

---

**ED Bot v8** - Reliable, Safe, Compliant Medical AI for Emergency Departments