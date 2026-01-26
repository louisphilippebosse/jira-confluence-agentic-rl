# Makefile for Jira-Confluence Agentic AI

.PHONY: help install dev run docker-build docker-run clean test lint format

help:
	@echo "Available commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make dev          - Setup development environment"
	@echo "  make run          - Run the application locally"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run with Docker Compose"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"

install:
	pip install -r requirements.txt

dev:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "Development environment ready! Edit .env with your credentials."

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

test:
	pytest

lint:
	flake8 app/ --max-line-length=120

format:
	black app/
