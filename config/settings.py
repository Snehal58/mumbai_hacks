"""Application settings using Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import List


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
    
    # Database Configuration
    mongodb_url: str = "mongodb+srv://vijaydope023:DefpjJzv0qiBHSYc@cluster0.dmgpqfw.mongodb.net/meal_planner"
    
    # Application Configuration
    app_name: str = "AI Meal Planner"
    app_version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Session Configuration
    session_timeout: int = 3600
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

