"""Perplexity API service client for recipe search."""

import httpx
import json
from typing import List, Dict, Optional
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PerplexityService:
    """Client for Perplexity API."""
    
    BASE_URL = "https://api.perplexity.ai/chat/completions"
    
    def __init__(self):
        self.api_key = settings.perplexity_api_key
        # Perplexity model names: "sonar", "sonar-pro", "llama-3.1-sonar-large-128k-online", etc.
        self.model = getattr(settings, 'perplexity_model', 'llama-3.1-sonar-large-128k-online')
    
    async def search_recipes(
        self,
        query: str = "",
        min_protein: Optional[float] = None,
        max_calories: Optional[float] = None,
        cuisine: Optional[str] = None,
        diet: Optional[List[str]] = None,
        meal_type: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Search for recipes using Perplexity AI.
        
        Uses Perplexity's chat API to find recipes based on the provided criteria.
        """
        if not self.api_key:
            logger.warning("Perplexity API key not configured")
            return []
        
        # Build a comprehensive prompt for recipe search
        prompt_parts = []
        
        if query:
            prompt_parts.append(f"Find recipes for: {query}")
        else:
            prompt_parts.append("Find recipes")
        
        if meal_type:
            prompt_parts.append(f"for {meal_type}")
        
        if cuisine:
            prompt_parts.append(f"with {cuisine} cuisine")
        
        if diet:
            prompt_parts.append(f"that are {', '.join(diet)}")
        
        if max_calories:
            prompt_parts.append(f"with maximum {max_calories} calories")
        
        if min_protein:
            prompt_parts.append(f"with at least {min_protein}g of protein")
        
        prompt_parts.append(f"Return exactly {max_results} recipes.")
        prompt_parts.append("For each recipe, provide:")
        prompt_parts.append("- Title")
        prompt_parts.append("- List of ingredients")
        prompt_parts.append("- Brief cooking instructions (3-5 steps)")
        prompt_parts.append("- Estimated nutrition info (calories, protein in grams, carbs in grams, fats in grams)")
        prompt_parts.append("- Prep time and cook time in minutes (if available)")
        prompt_parts.append("- Number of servings")
        prompt_parts.append("")
        prompt_parts.append("Format the response as a JSON array of recipe objects with these fields:")
        prompt_parts.append('{"title": "...", "ingredients": [...], "instructions": [...], "nutrition": {"calories": ..., "protein": ..., "carbs": ..., "fats": ...}, "prep_time": ..., "cook_time": ..., "servings": ...}')
        prompt_parts.append("Return ONLY valid JSON, no additional text.")
        
        prompt = " ".join(prompt_parts)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful recipe assistant. Always return recipe information in valid JSON format as requested."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4000
                    },
                    timeout=30.0
                )
                
                # Log error details if request failed
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Perplexity API error ({response.status_code}): {error_detail}")
                    try:
                        error_json = response.json()
                        logger.error(f"Error details: {error_json}")
                    except:
                        pass
                
                response.raise_for_status()
                data = response.json()
                
                # Extract the content from the response
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                if not content:
                    logger.warning("Empty response from Perplexity API")
                    return []
                
                # Try to parse JSON from the response
                # Sometimes the response might have markdown code blocks
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.startswith("```"):
                    content = content[3:]  # Remove ```
                if content.endswith("```"):
                    content = content[:-3]  # Remove closing ```
                content = content.strip()
                
                try:
                    recipes_data = json.loads(content)
                    # If it's a single recipe object, wrap it in a list
                    if isinstance(recipes_data, dict):
                        recipes_data = [recipes_data]
                    
                    recipes = []
                    for recipe in recipes_data[:max_results]:
                        # Normalize the recipe data to match expected format
                        recipes.append({
                            "id": f"perplexity_{hash(recipe.get('title', ''))}",
                            "title": recipe.get("title", ""),
                            "description": recipe.get("description", ""),
                            "ingredients": recipe.get("ingredients", []),
                            "instructions": recipe.get("instructions", []),
                            "nutrition": recipe.get("nutrition", {
                                "calories": 0,
                                "protein": 0,
                                "carbs": 0,
                                "fats": 0
                            }),
                            "prep_time": recipe.get("prep_time"),
                            "cook_time": recipe.get("cook_time"),
                            "servings": recipe.get("servings"),
                            "image_url": recipe.get("image_url", ""),
                            "source_url": recipe.get("source_url", ""),
                        })
                    
                    return recipes
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from Perplexity response: {e}")
                    logger.debug(f"Response content: {content[:500]}")
                    # Fallback: try to extract recipe information from text
                    return self._parse_text_response(content, max_results)
                    
        except httpx.HTTPStatusError as e:
            # Log detailed error information for HTTP errors
            error_msg = f"HTTP {e.response.status_code} error from Perplexity API"
            try:
                error_detail = e.response.json()
                logger.error(f"{error_msg}: {error_detail}")
            except:
                logger.error(f"{error_msg}: {e.response.text}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error connecting to Perplexity API: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching recipes from Perplexity: {e}", exc_info=True)
            return []
    
    def _parse_text_response(self, content: str, max_results: int) -> List[Dict]:
        """Fallback method to parse recipe information from text response."""
        # This is a simple fallback - in production, you might want more sophisticated parsing
        recipes = []
        lines = content.split('\n')
        
        current_recipe = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to identify recipe titles (lines that look like titles)
            if line and len(line) < 100 and not line.startswith('-') and not line.startswith('*'):
                if current_recipe:
                    recipes.append(current_recipe)
                    if len(recipes) >= max_results:
                        break
                
                current_recipe = {
                    "id": f"perplexity_{hash(line)}",
                    "title": line,
                    "description": "",
                    "ingredients": [],
                    "instructions": [],
                    "nutrition": {
                        "calories": 0,
                        "protein": 0,
                        "carbs": 0,
                        "fats": 0
                    },
                    "prep_time": None,
                    "cook_time": None,
                    "servings": None,
                    "image_url": "",
                    "source_url": "",
                }
        
        if current_recipe and len(recipes) < max_results:
            recipes.append(current_recipe)
        
        return recipes[:max_results]
    
    async def search_restaurant_order_links(
        self,
        dish_name: str,
        location: str,
        platforms: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Search for direct order links from Swiggy/Zomato for a dish at restaurants in a location.
        
        Uses Perplexity's chat API to find restaurants serving the dish and their order links.
        
        Args:
            dish_name: Name of the dish (e.g., "paneer tikka")
            location: Location string (e.g., "Kharadi, Pune")
            platforms: List of platforms to search (e.g., ["swiggy", "zomato"])
            max_results: Maximum number of results to return
            
        Returns:
            List of restaurant dictionaries with order links
        """
        if not self.api_key:
            logger.warning("Perplexity API key not configured")
            return []
        
        platform_str = " or ".join(platforms) if platforms else "Swiggy or Zomato"
        
        prompt = f"""Search the web for restaurants in {location} that serve {dish_name} and find their direct order links from {platform_str}.

You need to:
1. Find restaurants in {location} that serve {dish_name}
2. Search for their presence on {platform_str}
3. Extract or construct the direct order URLs for {dish_name} from these restaurants
4. Provide actual, working URLs that users can click to order

For each restaurant, provide:
- restaurant_name: Full name of the restaurant
- dish_name: The dish name (should be {dish_name} or similar variant)
- order_link: Direct URL to order this dish from {platform_str} (must be a full https:// URL)
- rating: Restaurant rating if available (number between 0-5)
- price: Estimated price in INR if available (number)
- address: Restaurant address or area in {location}
- platform: Either "swiggy" or "zomato"

The order_link must be a real, clickable URL. You can construct URLs using patterns like:
- Swiggy: https://www.swiggy.com/restaurants/[restaurant-name]/[location-id] or search URLs
- Zomato: https://www.zomato.com/[city]/[restaurant-name]/order or direct dish URLs

Format the response as a JSON array. Example format:
[
  {{"restaurant_name": "Restaurant Name", "dish_name": "{dish_name}", "order_link": "https://www.swiggy.com/...", "rating": 4.2, "price": 250, "address": "...", "platform": "swiggy"}},
  {{"restaurant_name": "Another Restaurant", "dish_name": "{dish_name}", "order_link": "https://www.zomato.com/...", "rating": 4.5, "price": 300, "address": "...", "platform": "zomato"}}
]

Return exactly {max_results} restaurants. Return ONLY valid JSON array, no markdown, no code blocks, no additional text before or after."""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful restaurant finder assistant specialized in finding direct order links from food delivery platforms. You have access to real-time web search. Always search for actual restaurant listings on Swiggy and Zomato, extract or construct working order URLs, and return the information in valid JSON array format. Never return placeholder URLs - always provide real, clickable links that users can use to order."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4000
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Perplexity API error ({response.status_code}): {error_detail}")
                    try:
                        error_json = response.json()
                        logger.error(f"Error details: {error_json}")
                    except:
                        pass
                
                response.raise_for_status()
                data = response.json()
                
                # Extract the content from the response
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                if not content:
                    logger.warning("Empty response from Perplexity API")
                    return []
                
                # Try to parse JSON from the response
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.startswith("```"):
                    content = content[3:]  # Remove ```
                if content.endswith("```"):
                    content = content[:-3]  # Remove closing ```
                content = content.strip()
                
                try:
                    restaurants_data = json.loads(content)
                    # If it's a single restaurant object, wrap it in a list
                    if isinstance(restaurants_data, dict):
                        restaurants_data = [restaurants_data]
                    
                    restaurants = []
                    for restaurant in restaurants_data[:max_results]:
                        # Normalize the restaurant data
                        restaurants.append({
                            "restaurant_name": restaurant.get("restaurant_name", ""),
                            "dish_name": restaurant.get("dish_name", dish_name),
                            "order_link": restaurant.get("order_link", ""),
                            "rating": restaurant.get("rating"),
                            "price": restaurant.get("price"),
                            "address": restaurant.get("address", location),
                            "platform": restaurant.get("platform", ""),
                        })
                    
                    return restaurants
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from Perplexity response: {e}")
                    logger.debug(f"Response content: {content[:1000]}")
                    # Try to extract URLs and restaurant info from text response
                    restaurants = self._parse_text_for_restaurants(content, dish_name, location, max_results)
                    if restaurants:
                        return restaurants
                    # Return empty list if parsing fails completely
                    logger.warning("Could not extract restaurant information from Perplexity response")
                    return []
                    
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code} error from Perplexity API"
            try:
                error_detail = e.response.json()
                logger.error(f"{error_msg}: {error_detail}")
            except:
                logger.error(f"{error_msg}: {e.response.text}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error connecting to Perplexity API: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching restaurant order links from Perplexity: {e}", exc_info=True)
            return []
    
    def _parse_text_for_restaurants(self, content: str, dish_name: str, location: str, max_results: int) -> List[Dict]:
        """Fallback method to extract restaurant information from text response."""
        import re
        restaurants = []
        
        # Try to find URLs in the text
        url_pattern = r'https?://(?:www\.)?(swiggy|zomato)\.com[^\s\)]+'
        urls = re.findall(url_pattern, content, re.IGNORECASE)
        
        # Try to find restaurant names (lines that might be restaurant names)
        lines = content.split('\n')
        restaurant_names = []
        for line in lines:
            line = line.strip()
            # Look for lines that might be restaurant names (not too long, not URLs, not JSON structure)
            if (line and len(line) < 80 and 
                not line.startswith('http') and 
                not line.startswith('{') and 
                not line.startswith('[') and
                'restaurant_name' not in line.lower() and
                len(line) > 0 and line[0].isupper()):
                restaurant_names.append(line)
        
        # Try to construct restaurant objects from found information
        for i, url_match in enumerate(re.finditer(url_pattern, content, re.IGNORECASE)):
            if i >= max_results:
                break
            url = url_match.group(0)
            platform = "swiggy" if "swiggy" in url.lower() else "zomato"
            restaurant_name = restaurant_names[i] if i < len(restaurant_names) else f"Restaurant in {location}"
            
            restaurants.append({
                "restaurant_name": restaurant_name,
                "dish_name": dish_name,
                "order_link": url,
                "rating": None,
                "price": None,
                "address": location,
                "platform": platform,
            })
        
        return restaurants[:max_results]

