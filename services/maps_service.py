"""Google Maps API service client."""

import httpx
from typing import List, Dict, Optional
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MapsService:
    """Client for Google Maps API."""
    
    BASE_URL = "https://maps.googleapis.com/maps/api"
    
    def __init__(self):
        self.api_key = settings.google_maps_api_key
    
    async def search_restaurants(
        self,
        location: str,
        query: str = "restaurant",
        cuisine_type: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Search for restaurants near a location."""
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return []
        
        search_query = query
        if cuisine_type:
            search_query = f"{cuisine_type} {query}"
        
        params = {
            "query": search_query,
            "location": location,
            "key": self.api_key,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Using Places API Text Search
                response = await client.get(
                    f"{self.BASE_URL}/place/textsearch/json",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                restaurants = []
                for place in data.get("results", [])[:max_results]:
                    restaurants.append({
                        "name": place.get("name", ""),
                        "address": place.get("formatted_address", ""),
                        "rating": place.get("rating"),
                        "price_level": place.get("price_level"),
                        "place_id": place.get("place_id", ""),
                        "location": place.get("geometry", {}).get("location", {}),
                        "types": place.get("types", []),
                    })
                
                return restaurants
        except Exception as e:
            logger.error(f"Error searching restaurants: {e}")
            return []
    
    async def get_place_details(self, place_id: str) -> Optional[Dict]:
        """Get detailed information about a place."""
        if not self.api_key:
            return None
        
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,rating,price_level,opening_hours,website,formatted_phone_number",
            "key": self.api_key,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/place/details/json",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", {})
        except Exception as e:
            logger.error(f"Error fetching place details: {e}")
            return None

