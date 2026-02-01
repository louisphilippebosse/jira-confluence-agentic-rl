FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run KG scripts on first run if needed, then start the app
CMD ["/bin/bash", "-c", "if [ ! -f /app/data/knowledge_graph.gpickle ]; then python -m app.maintenance.repopulate_kg && python -m app.maintenance.build_communities; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug"]
