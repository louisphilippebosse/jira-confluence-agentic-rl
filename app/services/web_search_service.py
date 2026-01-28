"""
Web Search Service using DuckDuckGo (no API key required)
Can be extended to use Tavily, SerpAPI, or other providers
"""
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class WebSearchService:
    """Simple web search service using DuckDuckGo HTML API"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web using DuckDuckGo
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results with title, url, snippet
        """
        try:
            logger.info(f"🌐 Searching web: {query}")
            
            # Try DuckDuckGo Instant Answer API first
            response = await self.client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1
                }
            )
            
            results = []
            
            if response.status_code == 200:
                data = response.json()
                
                # Get instant answer if available
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", "Summary"),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", ""),
                        "source": data.get("AbstractSource", "DuckDuckGo")
                    })
                
                # Get related topics
                for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else "Related",
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                            "source": "DuckDuckGo"
                        })
            
            # If we got results, return them
            if results:
                logger.info(f"✅ Found {len(results)} web results from instant answer API")
                return results[:max_results]
            
            # Fallback: Try DuckDuckGo HTML search
            logger.info("📡 No instant answers, trying HTML search...")
            html_response = await self.client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                follow_redirects=True
            )
            
            if html_response.status_code == 200:
                # Parse HTML for results (simple extraction)
                html_text = html_response.text
                
                # Extract result snippets (very basic parsing)
                import re
                # Look for result blocks in DuckDuckGo HTML
                result_blocks = re.findall(
                    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    html_text,
                    re.DOTALL
                )
                
                for url, title, snippet in result_blocks[:max_results]:
                    # Clean HTML tags
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    
                    if url and title:
                        results.append({
                            "title": title[:200],
                            "url": url,
                            "snippet": snippet[:300] if snippet else "No description available",
                            "source": "DuckDuckGo Search"
                        })
                
                if results:
                    logger.info(f"✅ Found {len(results)} web results from HTML search")
                    return results[:max_results]
            
            # If still no results, provide a helpful message
            logger.warning(f"⚠️ No web results found for: {query}")
            return [{
                "title": "Web Search Temporarily Limited",
                "url": "",
                "snippet": f"I found references to your search but couldn't retrieve live web data. For current information about '{query}', I recommend:\n\n1. Visit Google or DuckDuckGo directly\n2. Check official sources (weather.gc.ca for weather, news sites for news)\n3. Use specialized APIs for real-time data\n\nNote: This feature is in development. Consider integrating Tavily API or SerpAPI for better results.",
                "source": "System"
            }]
            
        except Exception as e:
            logger.error(f"Error searching web: {e}", exc_info=True)
            return [{
                "title": "Search Error",
                "url": "",
                "snippet": f"An error occurred while searching: {str(e)}",
                "source": "System"
            }]
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
web_search_service = WebSearchService()
