# UV Quick Start Guide

UV is an extremely fast Python package installer and resolver, written in Rust. It's a drop-in replacement for pip that can speed up your development workflow significantly.

## Installing UV

### macOS and Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### With pip
```bash
pip install uv
```

## Using UV with This Project

### Option 1: Quick Setup with UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
cd jira-confluence-agentic-rl

# Create virtual environment and install dependencies with UV
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (much faster than pip!)
uv pip install -r requirements.txt

# Or use pyproject.toml
uv pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: UV Sync (For Development)

```bash
# UV can also manage your entire environment
uv sync

# Run with UV
uv run uvicorn app.main:app --reload
```

## Speed Comparison

UV is significantly faster than traditional pip:

```
pip install -r requirements.txt    →  ~45 seconds
uv pip install -r requirements.txt →  ~2 seconds
```

That's **20x faster**!

## Common UV Commands

```bash
# Install a package
uv pip install fastapi

# Install from requirements.txt
uv pip install -r requirements.txt

# Install in editable mode
uv pip install -e .

# Update a package
uv pip install --upgrade langchain

# Create virtual environment
uv venv

# List installed packages
uv pip list

# Show package info
uv pip show networkx
```

## Using UV with Docker

You can also use UV in your Docker builds for faster builds:

```dockerfile
FROM python:3.11-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install with UV (much faster!)
RUN uv pip install --system -r requirements.txt

# Copy application
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Troubleshooting

### UV not found after installation
Add UV to your PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

### SSL Certificate errors
```bash
uv pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

## Learn More

- UV Documentation: https://github.com/astral-sh/uv
- UV Installation: https://astral.sh/uv
- Benchmarks: https://github.com/astral-sh/uv#benchmarks
