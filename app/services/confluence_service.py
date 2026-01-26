from atlassian import Confluence
from typing import List, Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ConfluenceService:
    """Read-only Confluence integration service"""
    
    def __init__(self):
        try:
            self.client = Confluence(
                url=settings.confluence_url,
                username=settings.confluence_username,
                password=settings.confluence_api_token
            )
            logger.info("Confluence client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Confluence client: {e}")
            self.client = None
    
    def search_content(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search Confluence content (read-only)"""
        if not self.client:
            return []
        
        try:
            results = self.client.cql(f'text ~ "{query}"', limit=limit)
            if not results or 'results' not in results:
                return []
            
            return [
                {
                    "id": item.get("content", {}).get("id"),
                    "title": item.get("content", {}).get("title"),
                    "type": item.get("content", {}).get("type"),
                    "space": item.get("content", {}).get("space", {}).get("name"),
                    "excerpt": item.get("excerpt", ""),
                }
                for item in results.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Error searching Confluence: {e}")
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


confluence_service = ConfluenceService()
