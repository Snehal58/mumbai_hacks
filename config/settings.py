"""Application settings using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import model_validator, computed_field
from typing import List, Any, Dict
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Anthropic Configuration (Optional)
    anthropic_api_key: str = ""
    
    # Edamam API
    edamam_app_id: str = ""
    edamam_app_key: str = ""
    
    # Spoonacular API
    spoonacular_api_key: str = ""
    
    # Google Maps API
    google_maps_api_key: str = ""
    
    # Perplexity API
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar"  # Alternative: "sonar" or "sonar-pro"
    
    # Database Configuration
    mongodb_url: str = "mongodb://localhost:27017/meal_planner"
    redis_url: str = "redis://localhost:6379/0"
    
    # Application Configuration
    app_name: str = "AI Meal Planner"
    app_version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Configuration - stored as string to avoid JSON parsing
    cors_origins_str: str = "http://localhost:3000,http://localhost:5173"
    
    @model_validator(mode='before')
    @classmethod
    def preprocess_cors_origins(cls, data: Any) -> Any:
        """Preprocess CORS_ORIGINS before Pydantic tries to JSON parse it."""
        if isinstance(data, dict):
            # Handle both uppercase and lowercase keys
            cors_key = None
            for key in data.keys():
                if key.lower() == 'cors_origins':
                    cors_key = key
                    break
            
            if cors_key and isinstance(data[cors_key], str):
                # If it's a string, check if it's JSON or comma-separated
                value = data[cors_key]
                try:
                    # Try to parse as JSON first
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        # It's valid JSON, keep it as is
                        data['cors_origins_str'] = ','.join(str(x) for x in parsed)
                    else:
                        # Not a list, treat as comma-separated
                        data['cors_origins_str'] = value
                except (json.JSONDecodeError, ValueError):
                    # Not JSON, treat as comma-separated string
                    data['cors_origins_str'] = value
                # Remove the original key to avoid conflicts
                if cors_key != 'cors_origins_str':
                    data.pop(cors_key, None)
        return data
    
    @computed_field
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins_str:
            return ["http://localhost:3000", "http://localhost:5173"]
        origins = [origin.strip() for origin in self.cors_origins_str.split(',') if origin.strip()]
        return origins if origins else ["http://localhost:3000", "http://localhost:5173"]
    
    # Session Configuration
    session_timeout: int = 3600
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

