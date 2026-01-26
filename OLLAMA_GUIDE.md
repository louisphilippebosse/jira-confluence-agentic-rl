# Ollama Setup Guide

Ollama allows you to run large language models locally on your machine, enabling fully private and offline AI capabilities.

## Why Ollama?

- ✅ **100% Local** - No data leaves your machine
- ✅ **No API Costs** - Free to use, unlimited requests
- ✅ **Privacy** - Your data stays private
- ✅ **Offline** - Works without internet
- ✅ **Fast** - With good hardware, responses are instant
- ✅ **Multiple Models** - Choose from many open-source models

## Installing Ollama

### macOS
```bash
brew install ollama
```

Or download from: https://ollama.ai/download

### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Windows
Download from: https://ollama.ai/download

## Starting Ollama

```bash
# Start Ollama service
ollama serve
```

This starts the Ollama server on `http://localhost:11434`

## Recommended Models

### For This Project

```bash
# Llama 3.2 (Recommended) - Fast and capable, 3B parameters
ollama pull llama3.2:latest

# Alternative: Mistral - Also excellent for structured tasks
ollama pull mistral:latest

# For better quality (needs more RAM/VRAM)
ollama pull llama3.1:8b
```

### Model Comparison

| Model | Size | RAM Needed | Speed | Quality |
|-------|------|------------|-------|---------|
| llama3.2 | 3B | 4GB | ⚡⚡⚡ | ★★★☆☆ |
| mistral | 7B | 8GB | ⚡⚡ | ★★★★☆ |
| llama3.1:8b | 8B | 8GB | ⚡⚡ | ★★★★☆ |
| llama3.1:70b | 70B | 64GB | ⚡ | ★★★★★ |

## Configuration

### Configure the Application

Edit your `.env` file:

```bash
# Use Ollama instead of OpenAI
LLM_PROVIDER=ollama

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# OpenAI key not needed when using Ollama
# OPENAI_API_KEY=
```

### Test Ollama

```bash
# Test if Ollama is running
curl http://localhost:11434/api/tags

# Chat with a model directly
ollama run llama3.2 "Hello, how are you?"
```

## Using with the Application

Once configured, the application will automatically use Ollama:

```bash
# Start the application
uvicorn app.main:app --reload

# The app will now use Ollama for all AI interactions
```

## Performance Tips

### GPU Acceleration

Ollama automatically uses your GPU if available:
- **NVIDIA GPUs**: Automatically detected (requires CUDA)
- **Apple Silicon (M1/M2/M3)**: Automatically uses Metal
- **AMD GPUs**: Supported on Linux with ROCm

### CPU-Only Mode

If you don't have a GPU, Ollama will use CPU (slower but works):

```bash
# Force CPU mode
OLLAMA_NUM_GPU=0 ollama serve
```

### Memory Management

```bash
# Limit memory usage (in GB)
OLLAMA_MAX_LOADED_MODELS=1 ollama serve

# Unload models when not in use
ollama stop llama3.2
```

## Advanced Usage

### Custom Model Parameters

You can customize model behavior by creating a Modelfile:

```bash
# Create a Modelfile
cat > Modelfile << 'EOF'
FROM llama3.2

# Set custom parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40

# Custom system message
SYSTEM You are a helpful assistant specialized in software engineering and project management.
EOF

# Create custom model
ollama create my-custom-model -f Modelfile

# Use in .env
OLLAMA_MODEL=my-custom-model
```

### Running Ollama as a Service

#### Linux (systemd)
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

#### macOS (launchd)
Ollama automatically starts as a service after installation.

#### Docker
```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Pull a model in the container
docker exec -it ollama ollama pull llama3.2
```

## Switching Between OpenAI and Ollama

You can easily switch between providers by changing the `.env` file:

```bash
# Use OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here

# Use Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```

No code changes needed - the application handles both!

## Troubleshooting

### Ollama not starting
```bash
# Check if port is in use
lsof -i :11434

# Kill existing process
killall ollama

# Restart
ollama serve
```

### Model download fails
```bash
# Try with explicit pull
ollama pull llama3.2:latest

# Check disk space
df -h

# Check Ollama status
ollama list
```

### Out of memory errors
Try a smaller model:
```bash
ollama pull llama3.2:1b  # Smallest version
```

### Slow responses
1. Use GPU acceleration if available
2. Try a smaller model
3. Reduce context window in code
4. Close other applications

## Resources

- Ollama Official Site: https://ollama.ai
- Model Library: https://ollama.ai/library
- GitHub: https://github.com/ollama/ollama
- Discord Community: https://discord.gg/ollama

## Comparison: OpenAI vs Ollama

| Feature | OpenAI | Ollama |
|---------|--------|--------|
| Cost | Pay per token | Free |
| Privacy | Data sent to OpenAI | 100% local |
| Internet | Required | Not required |
| Speed | Fast | Depends on hardware |
| Quality | Excellent | Good to Excellent |
| Setup | Just API key | Install + download models |
| Hardware | None needed | RAM/GPU recommended |

Choose Ollama for privacy and cost, OpenAI for ease of use and top quality!
