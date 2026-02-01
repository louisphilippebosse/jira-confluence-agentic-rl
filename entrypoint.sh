#!/bin/bash
set -e

# Start Ollama in the background
/bin/ollama serve &
pid=$!

# Wait a few seconds for Ollama to start
sleep 5

MODEL_NAME="${OLLAMA_MODEL:-llama3:8b}"
echo "🔴 Retrieving $MODEL_NAME model..."
ollama pull "$MODEL_NAME"

echo "🟢 Model pull complete!"

# Wait for Ollama process to finish
wait $pid