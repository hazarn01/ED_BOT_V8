# ED Bot v8 - Instructions to Start

## 📋 Table of Contents
1. [How to Start the Bot](#how-to-start-the-bot)
2. [LLM Models Available](#llm-models-available)
3. [How to Change LLM Backend](#how-to-change-llm-backend)
4. [Requirements & Dependencies](#requirements--dependencies)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 How to Start the Bot

### Option 1: Quick Start (Recommended)
```bash
# 1. Navigate to project directory
cd /Users/nimayh/Desktop/NH/V8/V8_azure

# 2. Set Python path and start server
PYTHONPATH=. python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001 --reload

# 3. Access the bot
# Web Interface: http://localhost:8001
# API Documentation: http://localhost:8001/docs
# Health Check: http://localhost:8001/health
```

### Option 2: Background Service
```bash
# Start in background
PYTHONPATH=. nohup python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001 > bot.log 2>&1 &

# Check logs
tail -f bot.log

# Stop service
pkill -f uvicorn
```

### Option 3: Using Makefile (if Docker available)
```bash
# Complete setup (first time)
make dev-setup

# Start services
make up

# Check health
make health

# View logs
make logs

# Stop services
make down
```

---

## 🤖 LLM Models Available

### Current Configuration (Azure OpenAI)
- **Primary Model**: `gpt-4o-mini`
- **Provider**: Azure OpenAI
- **Deployment**: `gpt-4o-mini`
- **Endpoint**: `https://oai-cbipm-01.openai.azure.com/`

### Alternative Models Supported
1. **Azure OpenAI Models:**
   - `gpt-4o-mini` (current)
   - `gpt-4o`
   - `gpt-4-turbo`
   - `gpt-3.5-turbo`

2. **Ollama Models:**
   - `llama3.2:latest`
   - `llama3:8b`
   - `mistral:7b`
   - `phi3:mini`
   - `qwen:7b`
   - `deepseek-r1:1.5b`

3. **GPT-OSS Models:**
   - `EleutherAI/gpt-neox-20b`
   - Custom vLLM deployments

---

## 🔄 How to Change LLM Backend

### Switch to Ollama (Local)

#### Step 1: Update Environment Variables
Edit `.env` file:
```bash
# Change these settings
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b
DISABLE_EXTERNAL_CALLS=true
USE_AZURE_FALLBACK=false

# Keep database settings as-is
DB_HOST=localhost
DB_PORT=5432
DB_USER=nimayh
DB_PASSWORD=
DB_NAME=edbotv8
```

#### Step 2: Install and Start Ollama
```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull desired model
ollama pull mistral:7b
# OR
ollama pull llama3.2:latest
```

#### Step 3: Restart Bot
```bash
# Stop current instance
pkill -f uvicorn

# Start with new configuration
PYTHONPATH=. python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001 --reload
```

### Switch to Mistral 7B Specifically

#### Method 1: Via Ollama (Recommended)
```bash
# In .env file
LLM_BACKEND=ollama
OLLAMA_MODEL=mistral:7b

# Pull model
ollama pull mistral:7b
```

#### Method 2: Via vLLM (Advanced)
```bash
# In .env file
LLM_BACKEND=gpt-oss
VLLM_BASE_URL=http://localhost:8000
GPT_OSS_MODEL=mistralai/Mistral-7B-Instruct-v0.1

# Start vLLM server separately
pip install vllm
python -m vllm.entrypoints.openai.api_server --model mistralai/Mistral-7B-Instruct-v0.1 --port 8000
```

### Switch Back to Azure OpenAI
```bash
# In .env file
LLM_BACKEND=azure
AZURE_OPENAI_ENDPOINT=https://oai-cbipm-01.openai.azure.com/
AZURE_OPENAI_API_KEY=cb0e51bd1e4a46fbb4043b8bcdd04cd7
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
DISABLE_EXTERNAL_CALLS=false
USE_AZURE_FALLBACK=true
```

---

## 📦 Requirements & Dependencies

### System Requirements
- **Python**: 3.11+ (recommended 3.13)
- **Operating System**: macOS, Linux, Windows
- **Memory**: 8GB RAM minimum, 16GB recommended
- **Storage**: 5GB free space

### Python Dependencies (requirements.v8.txt)
```bash
# Install all dependencies
pip install -r requirements.v8.txt

# Key packages include:
# - fastapi
# - uvicorn
# - sqlalchemy
# - psycopg2-binary
# - redis
# - pydantic
# - httpx
# - aiohttp
```

### Database Requirements
```bash
# PostgreSQL (required)
brew install postgresql
brew services start postgresql

# Create database
createdb edbotv8

# Redis (required)
brew install redis
brew services start redis
```

### Docker Requirements (Optional)
```bash
# If using Docker Compose
docker --version
docker-compose --version

# Start full stack
docker-compose -f docker-compose.v8.yml up -d
```

### API/Service Dependencies

#### For Azure OpenAI (Current Setup)
- **Required**: Azure OpenAI API key and endpoint
- **Network**: Internet connection required
- **Authentication**: API key in environment variables

#### For Ollama (Local LLM)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# OR on macOS
brew install ollama

# Start service
ollama serve

# Available models
ollama list
```

#### For GPT-OSS/vLLM
```bash
# Install vLLM
pip install vllm

# GPU support (optional)
pip install vllm[gpu]

# Start server
python -m vllm.entrypoints.openai.api_server --model EleutherAI/gpt-neox-20b
```

---

## 🔧 Configuration Files

### Environment Variables (.env)
```bash
# Copy template
cp .env.azure.clean .env

# Edit with your settings
nano .env
```

### Key Configuration Locations
- **Main Config**: `src/config/enhanced_settings.py`
- **LLM Settings**: `src/ai/` directory
- **API Routes**: `src/api/` directory
- **Database Models**: `src/models/` directory

---

## 🩺 Health Checks

### Verify System Health
```bash
# Basic health
curl http://localhost:8001/health

# Detailed health
curl http://localhost:8001/api/v1/health/detailed

# Test query
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the STEMI protocol?", "query_type": "PROTOCOL_STEPS"}'
```

### Expected Health Scores
- **Excellent**: 95-100% (all components healthy)
- **Good**: 85-94% (minor issues, system functional)
- **Warning**: 70-84% (some components down)
- **Critical**: <70% (major issues)

---

## 🚨 Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find and kill process on port 8001
lsof -ti:8001 | xargs kill -9

# Or use different port
python -m uvicorn src.api.app:app --port 8002
```

#### 2. Database Connection Failed
```bash
# Check PostgreSQL status
brew services list | grep postgresql

# Restart PostgreSQL
brew services restart postgresql

# Verify database exists
psql -l | grep edbotv8
```

#### 3. Redis Connection Failed
```bash
# Check Redis status
brew services list | grep redis

# Start Redis
brew services start redis

# Test connection
redis-cli ping
```

#### 4. Azure OpenAI API Issues
```bash
# Check API key and endpoint in .env
cat .env | grep AZURE

# Test connection manually
curl -H "api-key: YOUR_API_KEY" \
  "https://your-endpoint.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2023-12-01-preview"
```

#### 5. Ollama Model Issues
```bash
# Check Ollama status
ollama list

# Pull missing model
ollama pull mistral:7b

# Check Ollama logs
ollama logs
```

### Performance Optimization

#### For Azure OpenAI
- Monitor API rate limits
- Implement request caching
- Use appropriate model for workload

#### For Local Models (Ollama)
- Ensure sufficient RAM (8GB+ for 7B models)
- Use SSD storage for model files
- Consider GPU acceleration

---

## 📞 Support & Documentation

### Quick Commands Reference
```bash
# Start bot
PYTHONPATH=. python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001 --reload

# Check health
curl http://localhost:8001/health

# View logs
tail -f bot.log

# Test query
curl -X POST http://localhost:8001/api/v1/query -H "Content-Type: application/json" -d '{"query": "test"}'

# Stop bot
pkill -f uvicorn
```

### Important URLs
- **Web Interface**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **Metrics**: http://localhost:8001/metrics

### Configuration Summary
- **Current LLM**: Azure OpenAI (gpt-4o-mini)
- **Database**: PostgreSQL (edbotv8)
- **Cache**: Redis
- **Port**: 8001
- **Branch**: v8_azure

---

**Last Updated**: September 17, 2025  
**Version**: ED Bot v8 with Azure OpenAI Integration  
**Status**: ✅ Production Ready