"""
Web Search Service using DuckDuckGo (no API key required).

This module provides web search functionality with content scraping.
It was moved from integrations/web/ to tools/web/ for better semantic organization.
"""
import logging
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class WebSearchService:
    """Web search service with content scraping"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            follow_redirects=True
        )
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure it has proper protocol and extract from redirects"""
        if not url:
            return url
        
        # Extract actual URL from DuckDuckGo redirect links
        # Format: https://duckduckgo.com/l/?uddg=<encoded_url>&rut=...
        if 'duckduckgo.com/l/' in url and 'uddg=' in url:
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                if 'uddg' in query_params:
                    # Extract and decode the actual URL
                    url = unquote(query_params['uddg'][0])
                    logger.info(f"Extracted URL from DDG redirect: {url[:80]}...")
            except Exception as e:
                logger.warning(f"Failed to extract URL from redirect: {e}")
        
        # Handle protocol-relative URLs (//example.com)
        if url.startswith('//'):
            url = 'https:' + url
        # Handle relative URLs (/path)
        elif url.startswith('/'):
            # Can't resolve relative URLs without base, return as-is
            return url
        # Ensure https if no protocol
        elif not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
    
    async def scrape_page_content(self, url: str) -> Dict[str, Any]:
        """
        Scrape actual content from a webpage
        
        Args:
            url: URL to scrape
            
        Returns:
            Dict with title, text content, and metadata
        """
        try:
            # Normalize URL to ensure proper protocol
            url = self._normalize_url(url)
            logger.info(f"Scraping content from: {url[:80]}...")
            
            response = await self.client.get(url, timeout=10.0)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get page title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "No title"
            
            # Try to find main content (common patterns)
            main_content = None
            
            # Look for article content (news sites, blogs)
            article = soup.find('article') or soup.find('main') or soup.find(class_=re.compile('content|article|post|entry', re.I))
            
            if article:
                main_content = article.get_text(separator='\n', strip=True)
            else:
                # Fallback: get all paragraph text
                paragraphs = soup.find_all('p')
                main_content = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
            
            # Clean up text
            lines = [line.strip() for line in main_content.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Limit content size
            if len(clean_text) > 3000:
                clean_text = clean_text[:3000] + "...\n[Content truncated for brevity]"
            
            # Extract metadata
            description = soup.find('meta', attrs={'name': 'description'})
            description_text = description.get('content', '') if description else ''
            
            # Extract relevant internal links for deeper scraping
            relevant_links = []
            from urllib.parse import urljoin, urlparse
            
            # Keywords that suggest pages with event/competition details
            event_keywords = ['event', 'competition', 'schedule', 'calendar', 'beast', 'competition', 
                            'tournament', 'championship', 'about', 'details', 'info']
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text().strip().lower()
                
                # Check if link text or href contains event keywords
                if any(keyword in link_text or keyword in href.lower() for keyword in event_keywords):
                    # Convert relative URLs to absolute
                    full_url = urljoin(url, href)
                    
                    # Only include links from same domain
                    if urlparse(full_url).netloc == urlparse(url).netloc:
                        relevant_links.append({
                            'url': full_url,
                            'text': link.get_text().strip()
                        })
            
            # Limit to top 3 most relevant links
            relevant_links = relevant_links[:3]
            
            logger.info(f"Scraped {len(clean_text)} characters from page")
            if relevant_links:
                logger.info(f"Found {len(relevant_links)} relevant internal links for deeper scraping")
            
            return {
                "title": title_text,
                "content": clean_text,
                "description": description_text,
                "url": url,
                "success": True,
                "related_links": relevant_links
            }
            
        except httpx.TimeoutException:
            logger.warning(f"Timeout scraping {url}")
            return {"error": "Timeout", "url": url}
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"error": str(e), "url": url}
    
    async def search(self, query: str, max_results: int = 5, scrape_content: bool = True) -> List[Dict[str, Any]]:
        """
        Search the web using DuckDuckGo and optionally scrape page content
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            scrape_content: If True, scrape actual content from top results
            
        Returns:
            List of search results with title, url, snippet, and optionally full content
        """
        try:
            logger.info(f"Searching web: {query}")
            
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
                logger.info(f"Found {len(results)} web results from instant answer API")
                
                # Scrape content from top results if requested
                if scrape_content:
                    logger.info(f"Scraping content from top {min(2, len(results))} results...")
                    for i, result in enumerate(results[:2]):  # Scrape top 2 results
                        if result.get("url"):
                            # Normalize URL before scraping
                            normalized_url = self._normalize_url(result["url"])
                            result["url"] = normalized_url
                            
                            scraped = await self.scrape_page_content(normalized_url)
                            if scraped.get("success"):
                                result["scraped_content"] = scraped.get("content", "")
                                result["full_title"] = scraped.get("title", result["title"])
                                logger.info(f"  Scraped result {i+1}")
                                
                                # Check for relevant internal links and scrape those too
                                related_links = scraped.get("related_links", [])
                                if related_links:
                                    logger.info(f"  Following {len(related_links)} internal links for deeper context...")
                                    additional_content = []
                                    for link in related_links[:2]:
                                        link_url = link.get("url")
                                        link_text = link.get("text")
                                        logger.info(f"    Scraping: {link_text[:50]}...")
                                        
                                        link_scraped = await self.scrape_page_content(link_url)
                                        if link_scraped.get("success"):
                                            additional_content.append(f"\n--- From linked page: {link_text} ---\n{link_scraped.get('content', '')[:1000]}")
                                    
                                    if additional_content:
                                        result["scraped_content"] += "\n\n" + "\n".join(additional_content)
                                        logger.info(f"  Added context from {len(additional_content)} related pages")
                            else:
                                logger.warning(f"  Failed to scrape result {i+1}: {scraped.get('error')}")
                
                return results[:max_results]
            
            # Fallback: Try DuckDuckGo HTML search
            logger.info("No instant answers, trying HTML search...")
            html_response = await self.client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                follow_redirects=True
            )
            
            if html_response.status_code == 200:
                html_text = html_response.text
                
                # Extract result snippets (very basic parsing)
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
                        result = {
                            "title": title[:200],
                            "url": url,
                            "snippet": snippet[:300] if snippet else "No description available",
                            "source": "DuckDuckGo Search"
                        }
                        results.append(result)
                
                if results:
                    logger.info(f"Found {len(results)} web results from HTML search")
                    
                    # Scrape content from top results if requested
                    if scrape_content:
                        logger.info(f"Scraping content from top {min(2, len(results))} results...")
                        for i, result in enumerate(results[:2]):
                            if result.get("url"):
                                normalized_url = self._normalize_url(result["url"])
                                result["url"] = normalized_url
                                
                                scraped = await self.scrape_page_content(normalized_url)
                                if scraped.get("success"):
                                    result["scraped_content"] = scraped.get("content", "")
                                    result["full_title"] = scraped.get("title", result["title"])
                                    logger.info(f"  Scraped result {i+1}")
                                else:
                                    logger.warning(f"  Failed to scrape result {i+1}: {scraped.get('error')}")
                    
                    return results[:max_results]
            
            # If still no results, provide a helpful message
            logger.warning(f"No web results found for: {query}")
            return [{
                "title": "Web Search Temporarily Limited",
                "url": "",
                "snippet": f"I found references to your search but couldn't retrieve live web data. For current information about '{query}', I recommend checking official sources or specialized search engines.",
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
