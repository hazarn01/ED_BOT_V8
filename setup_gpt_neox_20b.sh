#!/bin/bash
# Setup script for running GPT-NeoX-20B on CPU with 128GB RAM

echo "🚀 Setting up GPT-NeoX-20B for CPU inference..."

# Option 1: Use Ollama (Easiest)
echo "Installing GPT-NeoX-20B via Ollama..."

# Stop the broken vLLM container
docker.exe compose -f docker-compose.v8.yml down gpt-oss

# Start Ollama instead
docker.exe run -d \
  --name ollama-gpt-neox \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  --memory="90g" \
  --cpus="16" \
  ollama/ollama

# Wait for Ollama to start
sleep 5

# Pull a quantized version that fits in memory
echo "Pulling quantized GPT-NeoX model (this may take 10-20 minutes)..."
docker.exe exec ollama-gpt-neox ollama pull gptneox:20b-q4_K_M

echo "✅ GPT-NeoX-20B is ready for CPU inference!"
echo ""
echo "To test it directly:"
echo "  docker.exe exec -it ollama-gpt-neox ollama run gptneox:20b-q4_K_M"
echo ""
echo "API endpoint: http://localhost:11434/api/generate"