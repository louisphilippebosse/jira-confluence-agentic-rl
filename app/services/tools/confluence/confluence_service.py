"""
Confluence Service - Direct Confluence API operations.

This module provides the core Confluence API functionality. It was moved from
integrations/atlassian/confluence/ to tools/confluence/ for better semantic organization.

All Confluence-related code is now consolidated in one place following SOLID principles.
"""
from atlassian import Confluence
from typing import List, Dict, Any, Optional
from app.config import settings
import logging
import re

logger = logging.getLogger(__name__)


class ConfluenceService:
    """Read-only Confluence integration service"""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Confluence client"""
        if self._client is None:
            try:
                self._client = Confluence(
                    url=settings.confluence_url,
                    username=settings.confluence_username,
                    password=settings.confluence_api_token,
                    timeout=5
                )
                logger.info("Confluence client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Confluence client: {e}")
                self._client = False  # Mark as failed
        return self._client if self._client is not False else None
    
    def search_content(self, query: str, limit: int = 25, space_key: Optional[str] = None, fetch_full_content: bool = True) -> List[Dict[str, Any]]:
        """
        Search Confluence content including personal spaces (read-only)
        
        Args:
            query: Search query
            limit: Max results to return
            space_key: Optional space key to filter (e.g., '~7120200cdcd290d375488287f9f21afc27e59d' for personal space)
            fetch_full_content: If True, fetches full page content for better context extraction
        """
        if not self.client:
            return []
        
        try:
            # Extract keywords from query (remove common question words)
            keywords = re.sub(r'\b(tell me about|when does|what is|how|where|the|a|an|for)\b', '', query.lower(), flags=re.IGNORECASE)
            keywords = ' '.join(keywords.split())  # Clean up extra spaces
            search_query = keywords if keywords else query
            
            logger.info(f"Extracted search keywords: '{search_query}' from: '{query}'")
            
            # Build CQL query - try space filter first, fall back to all spaces
            if space_key:
                # Try with space filter first
                cql_query = f'type=page AND space="{space_key}" AND text ~ "{search_query}"'
                logger.info(f"Searching Confluence with space filter: {cql_query}")
                results = self.client.cql(cql_query, limit=limit, expand='space')
                
                # If no results with space filter, try without it and log warning
                results_count = len(results.get('results', [])) if results else 0
                if results_count == 0:
                    logger.warning(f"No results with space filter '{space_key}', trying without filter...")
                    cql_query = f'type=page AND text ~ "{search_query}"'
                    logger.info(f"Retrying with: {cql_query}")
                    results = self.client.cql(cql_query, limit=limit, expand='space')
                    results_count = len(results.get('results', [])) if results else 0
                    if results_count > 0:
                        logger.info(f"Found {results_count} pages without space filter")
                        # Log the spaces found to help debug
                        spaces_found = {r.get('content', {}).get('space', {}).get('key') for r in results['results']}
                        logger.warning(f"Pages found in spaces: {spaces_found} - your space key '{space_key}' may be incorrect")
            else:
                # No space filter
                cql_query = f'type=page AND text ~ "{search_query}"'
                logger.info(f"Searching Confluence without space filter: {cql_query}")
                results = self.client.cql(cql_query, limit=limit, expand='space')
            
            if not results or 'results' not in results or len(results['results']) == 0:
                logger.info(f"No results found for query: {query} (keywords: {search_query})")
                return []
            
            logger.info(f"Found {len(results.get('results', []))} Confluence pages for query: {query}")
            
            pages = []
            for item in results.get("results", []):
                content_data = item.get("content", {})
                page_id = content_data.get("id")
                space_info = content_data.get("space", {})
                
                page_info = {
                    "id": page_id,
                    "title": content_data.get("title"),
                    "type": content_data.get("type"),
                    "space": space_info.get("key"),
                    "space_name": space_info.get("name"),
                    "excerpt": item.get("excerpt", ""),
                }
                
                # Fetch full content if requested and page_id exists
                if fetch_full_content and page_id:
                    try:
                        full_page = self.get_page(page_id)
                        if full_page and full_page.get("content"):
                            # Extract text content (strip HTML for better readability)
                            content_text = re.sub(r'<[^>]+>', ' ', full_page.get("content", ""))
                            content_text = re.sub(r'\s+', ' ', content_text).strip()
                            # Limit to first 2000 chars to avoid overwhelming context
                            page_info["content"] = content_text[:2000]
                            logger.info(f"Fetched full content for page: {page_info['title']} (space: {page_info['space']})")
                    except Exception as e:
                        logger.warning(f"Could not fetch full content for page {page_id}: {e}")
                        # Keep excerpt as fallback
                
                pages.append(page_info)
            
            return pages
            
        except Exception as e:
            logger.error(f"Error searching Confluence: {e}", exc_info=True)
            return []
    
    def get_all_pages(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get ALL pages from all spaces (read-only)"""
        if not self.client:
            logger.warning("Confluence client not available")
            return []
        
        try:
            logger.info(f"Fetching all Confluence pages (limit={limit})...")
            # Use CQL to get all pages across all spaces
            results = self.client.cql('type=page', limit=limit, expand='space,version,body.view')
            
            if not results or 'results' not in results:
                logger.warning("No Confluence pages found")
                return []
            
            pages = []
            for item in results.get("results", []):
                content = item.get("content", {})
                space_info = content.get("space", {})
                version_info = content.get("version", {})
                
                page = {
                    "id": content.get("id"),
                    "title": content.get("title"),
                    "type": content.get("type", "page"),
                    "space": space_info.get("key"),
                    "space_name": space_info.get("name"),
                    "content": item.get("excerpt", ""),  # Use excerpt for preview
                    "created": version_info.get("when") if version_info.get("number") == 1 else None,
                    "updated": version_info.get("when"),
                    "author": version_info.get("by", {}).get("displayName"),
                    "labels": [],  # Can be enhanced later
                }
                pages.append(page)
            
            logger.info(f"Found {len(pages)} Confluence pages across all spaces")
            return pages
            
        except Exception as e:
            logger.error(f"Error fetching all Confluence pages: {e}", exc_info=True)
            return []
    
    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Confluence page"""
        if not self.client:
            return None
        
        try:
            page = self.client.get_page_by_id(page_id, expand="body.storage,version,space")
            return {
                "id": page.get("id"),
                "title": page.get("title"),
                "space": page.get("space", {}).get("name"),
                "version": page.get("version", {}).get("number"),
                "content": page.get("body", {}).get("storage", {}).get("value", ""),
                "created": page.get("history", {}).get("createdDate"),
            }
        except Exception as e:
            logger.error(f"Error getting Confluence page {page_id}: {e}")
            return None
    
    def get_space_pages(self, space_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pages from a specific space"""
        if not self.client:
            return []
        
        try:
            pages = self.client.get_all_pages_from_space(space_key, limit=limit)
            return [
                {
                    "id": page.get("id"),
                    "title": page.get("title"),
                    "type": page.get("type"),
                }
                for page in pages
            ]
        except Exception as e:
            logger.error(f"Error getting pages from space {space_key}: {e}")
            return []


# Singleton instance
confluence_service = ConfluenceService()
