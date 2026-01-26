#!/bin/bash
# Quick start script for OTP service

set -e

echo "🚀 Starting ERPNext Order Promise Engine..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your ERPNext credentials."
    echo ""
fi

# Check if running in Docker
if [ "$1" == "docker" ]; then
    echo "🐳 Starting with Docker Compose..."
    docker-compose up --build
    exit 0
fi

# Local development setup
echo "📦 Installing dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created virtual environment"
fi

source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Run tests
echo "🧪 Running tests..."
pytest tests/unit/ -v --tb=short
echo ""

# Start service
echo "🌐 Starting OTP service..."
echo "📖 API docs will be available at: http://localhost:8001/docs"
echo ""
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
