# AI Agentic Meal Planning Application

An intelligent AI agent system for personalized meal planning, recipe recommendations, and nutrition tracking using LangGraph Supervisor, LangChain, and multiple specialized sub-agents.

## 🏗️ Architecture

The application uses a multi-agent architecture with the following components:

- **LangGraph Supervisor**: Orchestrates multiple specialized agents
- **WebSocket API**: Real-time communication between frontend and backend
- **Sub-Agents**:
  - Natural Language Understanding Agent
  - Recipe Finder Agent
  - Restaurant Finder Agent
  - Product Finder Agent
  - Nutrition Analysis Agent
  - Planning/Orchestration Agent

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- MongoDB (via Docker)
- Redis (via Docker)
- API Keys for:
  - OpenAI (GPT-4/GPT-5)
  - Edamam
  - Spoonacular
  - Google Maps
  - Perplexity

### Installation

1. **Clone and navigate to the repository:**
   ```bash
   cd Mumbai_hacks
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install spaCy language model:**
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

6. **Start services with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

7. **Run the application:**
   ```bash
   python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

## 📁 Project Structure

```
Mumbai_hacks/
├── agents/                 # Agent implementations
│   ├── __init__.py
│   ├── supervisor.py      # LangGraph Supervisor setup
│   ├── nlp_agent.py       # Natural Language Understanding
│   ├── recipe_agent.py    # Recipe Finder Agent
│   ├── restaurant_agent.py # Restaurant Finder Agent
│   ├── product_agent.py   # Product Finder Agent
│   ├── nutrition_agent.py # Nutrition Analysis Agent
│   └── planner_agent.py   # Planning/Orchestration Agent
├── api/                   # FastAPI application
│   ├── __init__.py
│   ├── main.py           # FastAPI app with WebSocket
│   ├── websocket_handler.py # WebSocket message handling
│   └── routes.py         # REST API routes (if needed)
├── config/               # Configuration files
│   ├── __init__.py
│   ├── settings.py       # Pydantic settings
│   └── agent_config.py   # Agent-specific configs
├── models/               # Data models
│   ├── __init__.py
│   ├── schemas.py        # Pydantic schemas
│   └── database.py       # Database models
├── services/            # External API services
│   ├── __init__.py
│   ├── edamam_service.py
│   ├── spoonacular_service.py
│   ├── maps_service.py
│   └── nutrition_service.py
├── utils/               # Utility functions
│   ├── __init__.py
│   ├── logger.py
│   └── helpers.py
├── tests/               # Test files
│   └── __init__.py
├── .env.example         # Example environment variables
├── .gitignore
├── docker-compose.yml   # Docker services configuration
├── Dockerfile          # Application Dockerfile
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## 🔌 WebSocket API

### Connection

Connect to: `ws://localhost:8000/ws`

### Message Format

**Client → Server:**
```json
{
  "prompt": "I need 200g protein daily. I live in Bangalore. Plan my meals for today within ₹1000",
  "session_id": "unique-session-id",
  "context": {
    "location": "Bangalore",
    "budget": 1000,
    "preferences": ["vegetarian", "indian"]
  }
}
```

**Server → Client:**
```json
{
  "type": "thinking",
  "content": "Analyzing your requirements...",
  "session_id": "unique-session-id"
}
```

```json
{
  "type": "finding_records",
  "content": "Searching for recipes matching your criteria...",
  "session_id": "unique-session-id"
}
```

```json
{
  "type": "searching_more",
  "content": "Expanding search to nearby restaurants...",
  "session_id": "unique-session-id"
}
```

```json
{
  "type": "output",
  "content": {
    "meal_plan": [...],
    "recommendations": [...],
    "nutrition_summary": {...}
  },
  "session_id": "unique-session-id"
}
```

## 🐳 Docker Setup

The `docker-compose.yml` includes:
- MongoDB for data storage
- Redis for caching and session management
- Application service

To start all services:
```bash
docker-compose up -d
```

To view logs:
```bash
docker-compose logs -f
```

## 🔧 Configuration

All configuration is managed through environment variables. See `.env.example` for required variables.

Key configurations:
- `OPENAI_API_KEY`: Your OpenAI API key
- `EDAMAM_APP_ID` & `EDAMAM_APP_KEY`: Edamam API credentials
- `SPOONACULAR_API_KEY`: Spoonacular API key
- `GOOGLE_MAPS_API_KEY`: Google Maps API key
- `MONGODB_URL`: MongoDB connection string
- `REDIS_URL`: Redis connection string

## 🧪 Testing

Run tests with:
```bash
pytest tests/
```

## 📝 Development

### Adding a New Agent

1. Create agent file in `agents/`
2. Implement agent logic with LangChain tools
3. Register agent in `agents/supervisor.py`
4. Add agent configuration in `config/agent_config.py`

### Adding a New API Service

1. Create service file in `services/`
2. Implement API client with error handling
3. Add service to agent tools

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License

## 🙏 Acknowledgments

- LangChain & LangGraph teams
- All API providers (Edamam, Spoonacular, etc.)

