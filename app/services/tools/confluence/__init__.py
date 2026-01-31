"""
Confluence Tool Package - All Confluence-related code consolidated here.

This package provides:
- ConfluenceTool: Implements BaseTool interface for Confluence operations
- ConfluenceService: Direct Confluence API calls
- ConfluenceIntentDetector: Confluence-specific intent detection
"""
from .confluence_tool import ConfluenceTool
from .confluence_intent import ConfluenceIntentDetector
from .confluence_service import ConfluenceService, confluence_service

__all__ = [
    "ConfluenceTool",
    "ConfluenceIntentDetector",
    "ConfluenceService",
    "confluence_service",
]
