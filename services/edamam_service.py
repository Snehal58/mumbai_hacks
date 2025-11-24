"""Edamam API service client."""

import httpx
from typing import List, Dict, Optional
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class EdamamService:
    """Client for Edamam Recipe API."""
    
    BASE_URL = "https://api.edamam.com/api/recipes/v2"
    
    def __init__(self):
        self.app_id = settings.edamam_app_id
        self.app_key = settings.edamam_app_key
    
    async def search_recipes(
        self,
        query: str = "",
        min_protein: Optional[float] = None,
        max_calories: Optional[float] = None,
        cuisine_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        diet: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Search for recipes matching criteria."""
        if not self.app_id or not self.app_key:
            logger.warning("Edamam credentials not configured")
            return []
        
        params = {
            "type": "public",
            "q": query,
            "app_id": self.app_id,
            "app_key": self.app_key,
            "to": max_results,
        }
        
        if min_protein:
            params["nutrients[PROCNT]"] = f"{min_protein}+"
        
        if max_calories:
            params["calories"] = f"0-{max_calories}"
        
        if cuisine_type:
            params["cuisineType"] = cuisine_type.lower()
        
        if meal_type:
            params["mealType"] = meal_type.lower()
        
        if diet:
            params["diet"] = ",".join([d.lower() for d in diet])
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                recipes = []
                for hit in data.get("hits", [])[:max_results]:
                    recipe = hit.get("recipe", {})
                    recipes.append({
                        "id": recipe.get("uri", "").split("#")[-1],
                        "title": recipe.get("label", ""),
                        "description": recipe.get("source", ""),
                        "ingredients": recipe.get("ingredientLines", []),
                        "nutrition": {
                            "calories": recipe.get("totalNutrients", {}).get("ENERC_KCAL", {}).get("quantity", 0),
                            "protein": recipe.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0),
                            "carbs": recipe.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0),
                            "fats": recipe.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0),
                        },
                        "image_url": recipe.get("image", ""),
                        "source_url": recipe.get("url", ""),
                        "servings": recipe.get("yield", 1),
                    })
                
                return recipes
        except Exception as e:
            logger.error(f"Error fetching recipes from Edamam: {e}")
            return []

