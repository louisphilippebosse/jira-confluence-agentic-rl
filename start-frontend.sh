#!/bin/bash

echo "🚀 Starting Jira-Confluence AI Assistant with React Frontend"
echo ""

# Check if FastAPI backend is running
if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "❌ FastAPI backend not running on port 8000"
    echo "Start it in another terminal: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
fi

# Start React frontend
echo "✅ Starting React frontend on port 3000..."
cd frontend && npm run dev
