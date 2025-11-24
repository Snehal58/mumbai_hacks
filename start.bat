@echo off
REM Quick start script for AI Meal Planner (Windows)

echo 🚀 Starting AI Meal Planner...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist "venv\.installed" (
    echo 📥 Installing dependencies...
    pip install -r requirements.txt
    python -m spacy download en_core_web_sm
    type nul > venv\.installed
)

REM Check if .env exists
if not exist ".env" (
    echo ⚙️  Creating .env file from example...
    copy env.example .env
    echo ⚠️  Please edit .env and add your API keys!
    echo    At minimum, you need OPENAI_API_KEY
    pause
)

REM Start Docker services
echo 🐳 Starting Docker services...
docker-compose up -d

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 5 /nobreak > nul

REM Start the application
echo 🎯 Starting FastAPI application...
echo    API: http://localhost:8000
echo    WebSocket: ws://localhost:8000/ws
echo    Docs: http://localhost:8000/docs
echo.
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

