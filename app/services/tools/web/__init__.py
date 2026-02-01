"""
Web Search Tool Package - Web search integration.
"""
from .web_tool import WebTool
from .web_intent import WebIntentDetector
from .web_search_service import WebSearchService, web_search_service

__all__ = [
    "WebTool",
    "WebIntentDetector",
    "WebSearchService",
    "web_search_service",
]
