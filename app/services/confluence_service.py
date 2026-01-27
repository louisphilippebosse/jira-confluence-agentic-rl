from atlassian import Confluence
from typing import List, Dict, Any, Optional
from app.config import settings
import logging

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
                    "space": item.get("content", {}).get("space", {}).get("key"),
                    "space_name": item.get("content", {}).get("space", {}).get("name"),
                    "excerpt": item.get("excerpt", ""),
                }
                for item in results.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Error searching Confluence: {e}")
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
            
            logger.info(f"✅ Found {len(pages)} Confluence pages across all spaces")
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


confluence_service = ConfluenceService()
