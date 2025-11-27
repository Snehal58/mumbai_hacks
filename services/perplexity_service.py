"""Perplexity API service client."""

import httpx
import json
import re
from typing import List, Dict, Optional, Any
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PerplexityService:
    """Client for Perplexity API."""
    
    BASE_URL = "https://api.perplexity.ai"
    
    def __init__(self):
        self.api_key = settings.perplexity_api_key
    
    async def search(
        self,
        query: str,
        model: str = "sonar",
        max_results: int = 5,
        search_domains: Optional[List[str]] = None
    ) -> Dict:
        """Search using Perplexity API.
        
        Args:
            query: Search query
            model: Perplexity model to use
            max_results: Maximum number of results (handled by Perplexity internally for online models)
            search_domains: Optional list of domains to search (e.g., ['swiggy.com', 'zomato.com'])
            
        Returns:
            Dictionary with search results including citations and content
        """
        if not self.api_key:
            logger.warning("Perplexity API key not configured")
            return {"content": "Perplexity API key not configured.", "citations": []}
        
        # Enhance query with domain filters if provided
        enhanced_query = query
        if search_domains:
            domain_filters = " OR ".join([f"site:{domain}" for domain in search_domains])
            enhanced_query = f"{query} ({domain_filters})"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that searches for products and food items. Provide detailed information including product names, prices, nutrition information, and links to purchase or order."
                },
                {
                    "role": "user",
                    "content": enhanced_query
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "top_p": 0.9
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Perplexity API error {response.status_code}: {error_text}")
                    try:
                        error_data = response.json()
                        logger.error(f"Error details: {json.dumps(error_data, indent=2)}")
                    except json.JSONDecodeError:
                        pass
                
                response.raise_for_status()
                data = response.json()
                
                # Extract content and citations
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Citations can be in different formats
                citations = []
                if "citations" in data:
                    citations = data.get("citations", [])
                elif "choices" in data and len(data.get("choices", [])) > 0:
                    # Sometimes citations are in the choice metadata
                    choice = data.get("choices", [{}])[0]
                    if "citations" in choice:
                        citations = choice.get("citations", [])
                    elif "message" in choice and "citations" in choice.get("message", {}):
                        citations = choice.get("message", {}).get("citations", [])
                
                return {
                    "content": content,
                    "citations": citations,
                    "raw_response": data
                }
        except httpx.RequestError as e:
            logger.error(f"Error fetching from Perplexity: {e}", exc_info=True)
            return {"content": f"Error fetching from Perplexity: {e}", "citations": []}
        except httpx.HTTPStatusError as e:
            logger.error(f"Perplexity API returned non-2xx status: {e}", exc_info=True)
            return {"content": f"Perplexity API error: {e.response.text}", "citations": []}
        except Exception as e:
            logger.error(f"An unexpected error occurred with Perplexity API: {e}", exc_info=True)
            return {"content": f"An unexpected error occurred: {e}", "citations": []}

    async def search_products(
        self,
        product_type: str,
        nutrition_goals: Optional[Dict[str, Any]] = None,
        location: Optional[str] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for products and food items using Perplexity.
        
        Args:
            product_type: Type of product to search for
            nutrition_goals: Optional nutrition requirements
            location: Optional location for local search
            max_results: Maximum number of results
            
        Returns:
            List of product dictionaries
        """
        # Build search query
        query_parts = [f"search for {product_type}"]
        
        if nutrition_goals:
            if nutrition_goals.get("protein"):
                query_parts.append(f"with {nutrition_goals.get('protein')}g protein")
            if nutrition_goals.get("calories"):
                query_parts.append(f"under {nutrition_goals.get('calories')} calories")
        
        if location:
            query_parts.append(f"in {location}")
        
        query_parts.append("include prices, nutrition information, and provide at least 5 different links to Swiggy and Zomato if available")
        
        query = " ".join(query_parts)
        
        # Search with Swiggy and Zomato domains
        search_domains = ["swiggy.com", "zomato.com"]
        
        result = await self.search(
            query=query,
            search_domains=search_domains,
            max_results=max(10, max_results * 2)  # Request more results to get more links
        )
        
        # Parse results and extract products
        products = self._parse_products_from_response(result, product_type)
        
        return products[:max_results]
    
    def _parse_products_from_response(
        self,
        response: Dict,
        product_type: str
    ) -> List[Dict[str, Any]]:
        """Parse Perplexity response to extract product information.
        
        Args:
            response: Perplexity API response
            product_type: Type of product searched
            
        Returns:
            List of parsed product dictionaries
        """
        products = []
        content = response.get("content", "")
        citations = response.get("citations", [])
        
        # Extract Swiggy and Zomato links from citations
        swiggy_links = []
        zomato_links = []
        
        for citation in citations:
            # Citations can be strings (URLs) or dictionaries
            if isinstance(citation, str):
                url = citation
                title = ""
                snippet = ""
            else:
                url = citation.get("url", "") or citation.get("link", "") or str(citation)
                title = citation.get("title", "") or citation.get("name", "")
                snippet = citation.get("snippet", "") or citation.get("text", "")
            
            if "swiggy.com" in url.lower():
                swiggy_links.append({
                    "url": url,
                    "title": title,
                    "snippet": snippet
                })
            elif "zomato.com" in url.lower():
                zomato_links.append({
                    "url": url,
                    "title": title,
                    "snippet": snippet
                })
        
        # Also search for links in the content text (more comprehensive pattern)
        # Match URLs more comprehensively, including those in markdown links
        url_patterns = [
            r'https?://(?:www\.)?(swiggy|zomato)\.com[^\s\)\]]+',  # Direct URLs
            r'\[([^\]]+)\]\((https?://(?:www\.)?(swiggy|zomato)\.com[^\)]+)\)',  # Markdown links
        ]
        
        for pattern in url_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                if len(match.groups()) > 1:
                    # Markdown link format
                    url = match.group(2)
                else:
                    # Direct URL
                    url = match.group(0)
                
                # Clean up URL (remove trailing punctuation)
                url = url.rstrip('.,;:!?)')
                
                if "swiggy" in url.lower() and not any(link["url"] == url for link in swiggy_links):
                    swiggy_links.append({"url": url, "title": "", "snippet": ""})
                elif "zomato" in url.lower() and not any(link["url"] == url for link in zomato_links):
                    zomato_links.append({"url": url, "title": "", "snippet": ""})
                
                # Stop if we have enough links
                if len(swiggy_links) + len(zomato_links) >= 10:  # Get more than 5 to have options
                    break
        
        # Try to extract product information from content
        # Parse structured content (markdown lists, numbered lists, etc.)
        lines = content.split("\n")
        current_product = None
        in_product_section = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Look for product entries (usually start with numbers, bullets, or bold text)
            is_product_start = (
                line.startswith("**") and not line.startswith("**Pricing") and not line.startswith("**Price") and
                not line.startswith("**Availability") and not line.startswith("**Nutritional")
            ) or (
                line and line[0].isdigit() and ("." in line[:3] or ")" in line[:3])
            ) or (
                line.startswith("- **") and not line.startswith("- **Price")
            )
            
            if is_product_start and not in_product_section:
                # Save previous product
                if current_product:
                    products.append(current_product)
                
                # Extract product name (remove markdown formatting)
                product_name = line
                product_name = product_name.replace("**", "").strip()
                product_name = re.sub(r'^\d+[.)]\s*', '', product_name)  # Remove numbering
                product_name = re.sub(r'^-\s*', '', product_name)  # Remove bullet
                
                # Skip if it's clearly not a product name
                skip_keywords = ["pricing", "price", "availability", "nutritional", "here are", 
                               "nutrition per", "protein:", "calories:", "carbs:", "fats:",
                               "protein per", "per serving", "per bar", "brand", "by:"]
                if any(skip in product_name.lower() for skip in skip_keywords):
                    continue
                
                # Skip if too short or looks like a label
                if len(product_name) < 3 or product_name.endswith(":"):
                    continue
                
                current_product = {
                    "name": product_name[:100],  # Limit length
                    "brand": "Unknown",
                    "nutrition": {
                        "calories": 0.0,
                        "protein": 0.0,
                        "carbs": 0.0,
                        "fats": 0.0,
                    },
                    "price": None,
                    "price_per_unit": None,
                    "description": "",
                    "swiggy_link": None,
                    "zomato_link": None,
                }
                in_product_section = True
            elif current_product:
                # Look for price information
                if any(keyword in line.lower() for keyword in ["₹", "rupees", "price", "rs.", "cost", "pricing"]):
                    price = self._extract_price(line)
                    if price:
                        current_product["price"] = price
                        current_product["price_per_unit"] = line[:100]
                
                # Look for nutrition information
                elif any(keyword in line.lower() for keyword in ["protein", "calories", "carbs", "fats", "nutrition"]):
                    nutrition = self._extract_nutrition(line)
                    if nutrition:
                        current_product["nutrition"].update(nutrition)
                
                # Look for brand information
                elif "brand" in line.lower() or "by " in line.lower():
                    brand_match = re.search(r'(?:brand|by)[:\s]+([^,\n]+)', line, re.IGNORECASE)
                    if brand_match:
                        current_product["brand"] = brand_match.group(1).strip()
                
                # Add to description (but skip markdown formatting lines)
                elif not line.startswith("**") and not line.startswith("#") and len(line) > 10:
                    if current_product["description"]:
                        current_product["description"] += " " + line
                    else:
                        current_product["description"] = line
                
                # Check if we're moving to next product (new numbered/bulleted item)
                if (line.startswith("**") and i < len(lines) - 1) or (line and line[0].isdigit() and "." in line[:3]):
                    # Might be next product, but continue collecting current one
                    pass
        
        if current_product:
            products.append(current_product)
        
        # Combine all links (up to 5 total: Swiggy and Zomato)
        all_links = []
        # Prioritize Swiggy links, then Zomato
        max_links = 5
        swiggy_count = min(len(swiggy_links), max_links)
        zomato_count = min(len(zomato_links), max(0, max_links - swiggy_count))
        
        # Add Swiggy links first
        for i in range(swiggy_count):
            all_links.append({
                "type": "swiggy",
                "url": swiggy_links[i]["url"],
                "title": swiggy_links[i].get("title", ""),
                "snippet": swiggy_links[i].get("snippet", "")
            })
        
        # Add Zomato links
        for i in range(zomato_count):
            all_links.append({
                "type": "zomato",
                "url": zomato_links[i]["url"],
                "title": zomato_links[i].get("title", ""),
                "snippet": zomato_links[i].get("snippet", "")
            })
        
        # Add links to products (distribute across products)
        for i, product in enumerate(products):
            # Assign primary link (Swiggy preferred, then Zomato)
            if i < len(swiggy_links):
                product["swiggy_link"] = swiggy_links[i]["url"]
            elif i < len(zomato_links):
                product["zomato_link"] = zomato_links[i]["url"]
            
            # Add all_links array to each product (up to 5 total links)
            product["links"] = all_links[:max_links]
        
        # If no products were parsed, create a generic product from the response
        if not products and content:
            # Combine all links (up to 5 total)
            max_links = 5
            all_links = []
            swiggy_count = min(len(swiggy_links), max_links)
            zomato_count = min(len(zomato_links), max(0, max_links - swiggy_count))
            
            for i in range(swiggy_count):
                all_links.append({
                    "type": "swiggy",
                    "url": swiggy_links[i]["url"],
                    "title": swiggy_links[i].get("title", ""),
                    "snippet": swiggy_links[i].get("snippet", "")
                })
            
            for i in range(zomato_count):
                all_links.append({
                    "type": "zomato",
                    "url": zomato_links[i]["url"],
                    "title": zomato_links[i].get("title", ""),
                    "snippet": zomato_links[i].get("snippet", "")
                })
            
            products.append({
                "name": product_type.title(),
                "brand": "Various",
                "nutrition": {
                    "calories": 0.0,
                    "protein": 0.0,
                    "carbs": 0.0,
                    "fats": 0.0,
                },
                "price": None,
                "price_per_unit": None,
                "description": content[:500],  # First 500 chars
                "swiggy_link": swiggy_links[0]["url"] if swiggy_links else None,
                "zomato_link": zomato_links[0]["url"] if zomato_links else None,
                "links": all_links[:max_links],  # Up to 5 links
            })
        
        return products
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text."""
        # Look for ₹ followed by numbers
        match = re.search(r'₹\s*(\d+(?:[.,]\d+)?)', text)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return float(price_str)
            except ValueError:
                pass
        return None
    
    def _extract_nutrition(self, text: str) -> Optional[Dict[str, float]]:
        """Extract nutrition information from text."""
        nutrition = {}
        
        # Look for protein
        match = re.search(r'protein[:\s]+(\d+(?:\.\d+)?)\s*g', text, re.IGNORECASE)
        if match:
            nutrition["protein"] = float(match.group(1))
        
        # Look for calories
        match = re.search(r'calories?[:\s]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if match:
            nutrition["calories"] = float(match.group(1))
        
        # Look for carbs
        match = re.search(r'carbs?[:\s]+(\d+(?:\.\d+)?)\s*g', text, re.IGNORECASE)
        if match:
            nutrition["carbs"] = float(match.group(1))
        
        # Look for fats
        match = re.search(r'fats?[:\s]+(\d+(?:\.\d+)?)\s*g', text, re.IGNORECASE)
        if match:
            nutrition["fats"] = float(match.group(1))
        
        return nutrition if nutrition else None

