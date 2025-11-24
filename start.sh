#!/bin/bash

# Quick start script for AI Meal Planner

echo "🚀 Starting AI Meal Planner..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    python -m spacy download en_core_web_sm
    touch venv/.installed
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from example..."
    cp env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
    echo "   At minimum, you need OPENAI_API_KEY"
    read -p "Press enter after updating .env..."
fi

# Start Docker services
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Start the application
echo "🎯 Starting FastAPI application..."
echo "   API: http://localhost:8000"
echo "   WebSocket: ws://localhost:8000/ws"
echo "   Docs: http://localhost:8000/docs"
echo ""
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

