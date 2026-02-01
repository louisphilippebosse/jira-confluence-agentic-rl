# Makefile for Jira-Confluence Agentic AI

.PHONY: help install install-uv dev dev-uv run docker-build docker-run clean test lint format

help:
	@echo "Available commands:"
	@echo "  make install-uv   - Install dependencies with UV (fastest)"
	@echo "  make install      - Install Python dependencies with pip"
	@echo "  make dev-uv       - Setup development environment with UV"
	@echo "  make dev          - Setup development environment with pip"
	@echo "  make run          - Run the application locally"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run with Docker Compose"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"

install-uv:
	uv pip install -r requirements.txt

install:
	pip install -r requirements.txt

dev-uv:
	uv venv
	. .venv/bin/activate && uv pip install -r requirements.txt
	cp .env.example .env
	@echo "Development environment ready with UV! Edit .env with your credentials."
	@echo "Activate with: source .venv/bin/activate"

dev:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "Development environment ready! Edit .env with your credentials."
	@echo "Activate with: source venv/bin/activate"

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t jira-confluence-ai .

docker-run:
	docker-compose up --build

docker-stop:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .venv venv

test:
	pytest

lint:
	flake8 app/ --max-line-length=120

format:
	black app/
