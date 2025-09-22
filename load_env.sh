#!/bin/bash
# Script to load environment variables from .env file, ignoring comments

if [ -f "$1" ]; then
    echo "Loading environment variables from $1..."
    
    # Export variables, ignoring comments and empty lines
    export $(grep -v '^#' "$1" | grep -v '^$' | xargs)
    
    echo "Environment variables loaded successfully!"
    echo "Current LLM_BACKEND: ${LLM_BACKEND:-not set}"
    echo "Current AZURE_OPENAI_ENDPOINT: ${AZURE_OPENAI_ENDPOINT:-not set}"
else
    echo "Environment file $1 not found!"
fi
