# Sample cURL Commands for Restaurant Order Links

## Get Direct Buy Links from Swiggy/Zomato for Paneer Tikka in Kharadi, Pune

### Basic Request

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Show me direct buy links from Swiggy or Zomato to order paneer tikka from restaurants in Kharadi, Pune",
    "session_id": "sample-session-123",
    "context": {
      "location": "Kharadi, Pune",
      "dish": "paneer tikka",
      "platforms": ["swiggy", "zomato"]
    }
  }'
```

### With More Context

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I want to order paneer tikka. Please provide direct purchase links from Swiggy or Zomato for restaurants in Kharadi, Pune area. Include restaurant names, ratings, and direct order links.",
    "session_id": "sample-session-123",
    "context": {
      "location": "Kharadi, Pune, Maharashtra, India",
      "dish": "paneer tikka",
      "platforms": ["swiggy", "zomato"],
      "meal_type": "dinner",
      "budget": null
    }
  }'
```

### Pretty-printed Response (using jq)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Show me direct buy links from Swiggy or Zomato to order paneer tikka from restaurants in Kharadi, Pune",
    "session_id": "sample-session-123",
    "context": {
      "location": "Kharadi, Pune",
      "dish": "paneer tikka"
    }
  }' | jq '.'
```

### Windows PowerShell Version

```powershell
$body = @{
    prompt = "Show me direct buy links from Swiggy or Zomato to order paneer tikka from restaurants in Kharadi, Pune"
    session_id = "sample-session-123"
    context = @{
        location = "Kharadi, Pune"
        dish = "paneer tikka"
        platforms = @("swiggy", "zomato")
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method Post -Body $body -ContentType "application/json"
```

## Expected Response Format

The API should return a response containing:
- Restaurant names serving paneer tikka in Kharadi, Pune
- Direct order links from Swiggy and/or Zomato
- Restaurant ratings and other relevant information
- Estimated prices

## Notes

- Replace `localhost:8000` with your actual server URL if different
- The `session_id` is optional but recommended for tracking conversations
- The `context` field helps provide location and preference information to the AI agent
- The response will be processed by the workflow supervisor which may use Perplexity or other services to find the restaurant links

