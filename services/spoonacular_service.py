"""Spoonacular API service client."""

import httpx
from typing import List, Dict, Optional
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SpoonacularService:
    """Client for Spoonacular API."""
    
    BASE_URL = "https://api.spoonacular.com"
    
    def __init__(self):
        self.api_key = settings.spoonacular_api_key
    
    async def search_recipes(
        self,
        query: str = "",
        min_protein: Optional[float] = None,
        max_calories: Optional[float] = None,
        cuisine: Optional[str] = None,
        diet: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Search for recipes matching criteria."""
        if not self.api_key:
            logger.warning("Spoonacular API key not configured")
            return []
        
        params = {
            "apiKey": self.api_key,
            "number": max_results,
            "addRecipeInformation": True,
            "addRecipeNutrition": True,
        }
        
        if query:
            params["query"] = query
        
        if min_protein:
            params["minProtein"] = min_protein
        
        if max_calories:
            params["maxCalories"] = max_calories
        
        if cuisine:
            params["cuisine"] = cuisine
        
        if diet:
            params["diet"] = ",".join(diet)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/recipes/complexSearch",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                recipes = []
                for recipe in data.get("results", [])[:max_results]:
                    nutrition = recipe.get("nutrition", {})
                    nutrients = nutrition.get("nutrients", [])
                    
                    nutrition_dict = {}
                    for nutrient in nutrients:
                        name = nutrient.get("name", "").lower()
                        amount = nutrient.get("amount", 0)
                        if "calorie" in name:
                            nutrition_dict["calories"] = amount
                        elif "protein" in name:
                            nutrition_dict["protein"] = amount
                        elif "carbohydrate" in name:
                            nutrition_dict["carbs"] = amount
                        elif "fat" in name:
                            nutrition_dict["fats"] = amount
                    
                    recipes.append({
                        "id": str(recipe.get("id", "")),
                        "title": recipe.get("title", ""),
                        "description": recipe.get("summary", "")[:200] if recipe.get("summary") else "",
                        "ingredients": [ing.get("name", "") for ing in recipe.get("extendedIngredients", [])],
                        "instructions": recipe.get("analyzedInstructions", [{}])[0].get("steps", []) if recipe.get("analyzedInstructions") else [],
                        "nutrition": nutrition_dict,
                        "prep_time": recipe.get("preparationMinutes"),
                        "cook_time": recipe.get("cookingMinutes"),
                        "servings": recipe.get("servings"),
                        "image_url": recipe.get("image", ""),
                        "source_url": recipe.get("sourceUrl", ""),
                    })
                
                return recipes
        except Exception as e:
            logger.error(f"Error fetching recipes from Spoonacular: {e}")
            return []
    
    async def get_recipe_nutrition(self, recipe_id: str) -> Optional[Dict]:
        """Get detailed nutrition information for a recipe."""
        if not self.api_key:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/recipes/{recipe_id}/nutritionWidget.json",
                    params={"apiKey": self.api_key},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching nutrition from Spoonacular: {e}")
            return None

