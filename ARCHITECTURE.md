# Architecture Overview

## System Architecture

The AI Meal Planner uses a **multi-agent architecture** orchestrated by LangGraph Supervisor. Here's how it works:

```
Frontend (WebSocket Client)
    ↓
FastAPI WebSocket Endpoint (/ws)
    ↓
WebSocket Handler
    ↓
LangGraph Supervisor
    ↓
┌─────────────────────────────────────┐
│  Agent Orchestration Flow:          │
│  1. NLP Agent (parse request)       │
│  2. Recipe Agent (find recipes)     │
│  3. Restaurant Agent (find places)  │
│  4. Planner Agent (create plan)     │
└─────────────────────────────────────┘
    ↓
Response via WebSocket
```

## Component Details

### 1. FastAPI Application (`api/main.py`)
- **WebSocket Endpoint:** `/ws` - Handles real-time bidirectional communication
- **REST Endpoints:** `/health`, `/` - Health checks and info
- **CORS:** Configured for frontend integration
- **Lifespan:** Manages MongoDB and Redis connections

### 2. WebSocket Handler (`api/websocket_handler.py`)
- Manages active WebSocket connections
- Parses incoming messages
- Sends progress updates (thinking, finding_records, searching_more, output)
- Handles errors gracefully

### 3. LangGraph Supervisor (`agents/supervisor.py`)
- **Purpose:** Orchestrates multiple specialized agents
- **Flow:**
  1. Receives user prompt
  2. Routes through agent pipeline
  3. Collects results from each agent
  4. Returns final output

**Agent Pipeline:**
```
User Prompt
    ↓
NLP Agent → Parsed Request (nutrition goals, meal context)
    ↓
Recipe Agent → Recipe suggestions
    ↓
Restaurant Agent → Restaurant options
    ↓
Planner Agent → Complete meal plan
    ↓
Final Output
```

### 4. Specialized Agents

#### NLP Agent (`agents/nlp_agent.py`)
- **Purpose:** Parse natural language into structured data
- **Input:** Free-form user prompt
- **Output:** Structured request with:
  - Nutrition goals (calories, protein, carbs, fats)
  - Meal context (location, budget, preferences)
- **Technology:** OpenAI GPT-4 with structured output

#### Recipe Agent (`agents/recipe_agent.py`)
- **Purpose:** Find recipes matching criteria
- **APIs Used:** Spoonacular, Edamam
- **Filters:** Nutrition goals, cuisine, dietary restrictions
- **Output:** List of recipes with nutrition info

#### Restaurant Agent (`agents/restaurant_agent.py`)
- **Purpose:** Find restaurant meals
- **APIs Used:** Google Maps Places API
- **Features:** Location-based search, cuisine filtering
- **Output:** Restaurant options with estimated nutrition

#### Product Agent (`agents/product_agent.py`)
- **Purpose:** Find nutrition products/supplements
- **Output:** Product recommendations (protein powders, etc.)

#### Nutrition Agent (`agents/nutrition_agent.py`)
- **Purpose:** Analyze and validate nutrition
- **Features:**
  - Calculate total nutrition
  - Validate against goals
  - Identify gaps
  - Provide recommendations

#### Planner Agent (`agents/planner_agent.py`)
- **Purpose:** Orchestrate and combine results
- **Responsibilities:**
  - Coordinate all agents
  - Create comprehensive meal plan
  - Optimize for goals and constraints
  - Generate explanations

### 5. Service Layer (`services/`)

#### Edamam Service
- Recipe search API
- Nutrition data
- Cuisine filtering

#### Spoonacular Service
- Recipe search with detailed nutrition
- Recipe analysis
- Ingredient information

#### Maps Service
- Restaurant search
- Location-based queries
- Place details

#### Nutrition Service
- Nutrition calculations
- Goal validation
- Meal analysis

### 6. Data Models (`models/schemas.py`)

**Key Models:**
- `WebSocketMessage`: Client → Server message format
- `WebSocketResponse`: Server → Client response format
- `ParsedRequest`: Structured user request
- `NutritionGoal`: Nutrition targets
- `MealContext`: Meal planning context
- `Recipe`: Recipe data structure
- `RestaurantMeal`: Restaurant meal data
- `MealPlan`: Complete meal plan
- `AgentOutput`: Final agent output

### 7. Configuration (`config/`)

#### Settings (`config/settings.py`)
- Environment variable management
- API keys
- Database URLs
- Server configuration

#### Agent Config (`config/agent_config.py`)
- Agent-specific prompts
- Model configurations
- Temperature settings
- System prompts

### 8. Database Layer (`models/database.py`)

#### MongoDB
- **Purpose:** Store meal plans, user preferences, history
- **Connection:** Async Motor client
- **Collections:** (to be defined based on needs)

#### Redis
- **Purpose:** Caching, session management
- **Use Cases:**
  - Cache API responses
  - Store session data
  - Rate limiting

## Message Flow

### WebSocket Message Format

**Client → Server:**
```json
{
  "prompt": "I need 200g protein daily. Plan my meals.",
  "session_id": "unique-id",
  "context": {
    "location": "Bangalore",
    "budget": 1000
  }
}
```

**Server → Client (Progress Updates):**
```json
{
  "type": "thinking",
  "content": "Analyzing your request...",
  "session_id": "unique-id",
  "timestamp": "2024-01-01T12:00:00"
}
```

```json
{
  "type": "finding_records",
  "content": "Found 5 recipes matching your criteria",
  "session_id": "unique-id"
}
```

```json
{
  "type": "searching_more",
  "content": "Searching for nearby restaurants...",
  "session_id": "unique-id"
}
```

```json
{
  "type": "output",
  "content": {
    "meal_plan": {...},
    "recommendations": [...],
    "nutrition_summary": {...}
  },
  "session_id": "unique-id"
}
```

## Technology Stack

### Core Frameworks
- **LangGraph:** Agent orchestration and workflow
- **LangChain:** LLM integration and tooling
- **FastAPI:** Web framework and WebSocket support

### LLMs
- **OpenAI GPT-4:** Primary LLM for all agents
- **spaCy:** NLP processing (optional)

### APIs & Services
- **Edamam:** Recipe search
- **Spoonacular:** Recipe and nutrition data
- **Google Maps:** Restaurant search
- **USDA FoodData:** Nutrition database (future)

### Infrastructure
- **MongoDB:** Primary database
- **Redis:** Caching and sessions
- **Docker:** Containerization
- **Uvicorn:** ASGI server

## Extension Points

### Adding a New Agent

1. Create agent file in `agents/`
2. Implement agent logic with LangChain tools
3. Add agent node to supervisor graph
4. Configure in `config/agent_config.py`

### Adding a New API Service

1. Create service file in `services/`
2. Implement API client with error handling
3. Add service to relevant agent
4. Update configuration

### Customizing Agent Behavior

- Modify prompts in `config/agent_config.py`
- Adjust agent logic in respective agent files
- Change workflow in `agents/supervisor.py`

## Performance Considerations

1. **Caching:** Use Redis for API responses
2. **Async Operations:** All I/O is async
3. **Connection Pooling:** MongoDB and Redis connections are pooled
4. **Rate Limiting:** Consider implementing for API calls
5. **Error Handling:** Graceful degradation if APIs fail

## Security Considerations

1. **API Keys:** Stored in environment variables
2. **Input Validation:** Pydantic schemas validate all inputs
3. **CORS:** Configured for specific origins
4. **Error Messages:** Don't expose sensitive information

## Future Enhancements

1. **User Profiles:** Store preferences and history
2. **Meal Tracking:** Track actual consumption
3. **Adaptive Learning:** Learn from user feedback
4. **Multi-language Support:** Support multiple languages
5. **Voice Interface:** Add voice input/output
6. **Mobile App:** Native mobile application
7. **Social Features:** Share meal plans
8. **Grocery Lists:** Generate shopping lists

