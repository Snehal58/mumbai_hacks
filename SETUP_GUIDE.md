# Setup Guide for AI Meal Planner

## Prerequisites

1. **Python 3.10+** - Install from [python.org](https://www.python.org/downloads/)
2. **Docker & Docker Compose** - Install from [docker.com](https://www.docker.com/get-started)
3. **API Keys** - You'll need keys for:
   - OpenAI (required) - Get from [platform.openai.com](https://platform.openai.com/api-keys)
   - Edamam (optional) - Get from [developer.edamam.com](https://developer.edamam.com/)
   - Spoonacular (optional) - Get from [spoonacular.com](https://spoonacular.com/food-api)
   - Google Maps (optional) - Get from [console.cloud.google.com](https://console.cloud.google.com/)
   - Perplexity (optional) - Get from [perplexity.ai](https://www.perplexity.ai/)

## Step-by-Step Setup

### 1. Clone and Navigate to Repository

```bash
cd Mumbai_hacks
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

### 5. Configure Environment Variables

Copy the example environment file:
```bash
# Windows
copy env.example .env

# Linux/Mac
cp env.example .env
```

Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=sk-your-actual-key-here
EDAMAM_APP_ID=your-app-id
EDAMAM_APP_KEY=your-app-key
SPOONACULAR_API_KEY=your-key-here
GOOGLE_MAPS_API_KEY=your-key-here
```

**Note:** At minimum, you need `OPENAI_API_KEY`. Other APIs are optional but enhance functionality.

### 6. Start Docker Services

Start MongoDB and Redis:
```bash
docker-compose up -d
```

Verify services are running:
```bash
docker-compose ps
```

### 7. Run the Application

**Development mode (with auto-reload):**
```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **HTTP:** http://localhost:8000
- **WebSocket:** ws://localhost:8000/ws
- **API Docs:** http://localhost:8000/docs

## Testing the Setup

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status": "healthy", "service": "AI Meal Planner"}
```

### 2. WebSocket Test

You can test the WebSocket using a simple Python script:

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        message = {
            "prompt": "I need 200g protein daily. I live in Bangalore. Plan my meals for today within ₹1000",
            "session_id": "test-session-123",
            "context": {
                "location": "Bangalore",
                "budget": 1000
            }
        }
        await websocket.send(json.dumps(message))
        
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Type: {data['type']}")
            print(f"Content: {data['content']}")
            if data['type'] == 'output':
                break

asyncio.run(test_websocket())
```

## Project Structure Overview

```
Mumbai_hacks/
├── agents/              # AI agent implementations
│   ├── supervisor.py   # LangGraph supervisor (orchestrator)
│   ├── nlp_agent.py    # Natural language understanding
│   ├── recipe_agent.py # Recipe finder
│   ├── restaurant_agent.py # Restaurant finder
│   ├── product_agent.py   # Product finder
│   ├── nutrition_agent.py # Nutrition analysis
│   └── planner_agent.py   # Meal planning orchestrator
├── api/                # FastAPI application
│   ├── main.py         # Main app with WebSocket
│   ├── websocket_handler.py # WebSocket message handling
│   └── routes.py       # REST API routes
├── config/             # Configuration
│   ├── settings.py     # Environment settings
│   └── agent_config.py # Agent configurations
├── models/             # Data models
│   ├── schemas.py      # Pydantic schemas
│   └── database.py     # Database connections
├── services/           # External API clients
│   ├── edamam_service.py
│   ├── spoonacular_service.py
│   ├── maps_service.py
│   └── nutrition_service.py
└── utils/              # Utilities
    ├── logger.py       # Logging setup
    └── helpers.py      # Helper functions
```

## Troubleshooting

### Issue: "Module not found" errors
**Solution:** Make sure virtual environment is activated and all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Issue: MongoDB connection error
**Solution:** Ensure Docker services are running:
```bash
docker-compose up -d
docker-compose logs mongodb
```

### Issue: OpenAI API errors
**Solution:** Verify your API key in `.env` file and check your OpenAI account has credits.

### Issue: spaCy model not found
**Solution:** Download the model:
```bash
python -m spacy download en_core_web_sm
```

### Issue: Port already in use
**Solution:** Change the port in `.env` or stop the process using port 8000.

## Next Steps

1. **Frontend Integration:** Connect your frontend to `ws://localhost:8000/ws`
2. **Customize Agents:** Modify agent configurations in `config/agent_config.py`
3. **Add More APIs:** Integrate additional food/nutrition APIs in `services/`
4. **Enhance Agents:** Add more sophisticated logic to agents in `agents/`

## Development Tips

- Use `--reload` flag for auto-reload during development
- Check logs in console for debugging
- Use FastAPI docs at `/docs` to test REST endpoints
- WebSocket messages are logged for debugging

## Production Deployment

For production:
1. Set `DEBUG=False` in `.env`
2. Use a production WSGI server (Gunicorn)
3. Set up proper CORS origins
4. Use environment-specific API keys
5. Set up monitoring and logging

