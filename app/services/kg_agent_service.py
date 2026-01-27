"""Knowledge Graph Agent - Preprocesses queries using cached graph data"""
import logging
from typing import Dict, List, Optional, Any
from app.services.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class KnowledgeGraphAgent:
    """Agent that uses the knowledge graph for fast preprocessing and context retrieval"""
    
    def __init__(self):
        self.kg = knowledge_graph_service
        logger.info("🕸️ Initialized Knowledge Graph Agent")
    
    def preprocess_query(self, message: str, conversation_history: List = None) -> Dict[str, Any]:
        """Preprocess a query using the knowledge graph to provide context
        
        Returns:
            Dict with:
            - relevant_entities: List of entities from KG related to the query
            - suggested_action: Recommended action based on KG analysis
            - context: Additional context from graph
            - needs_external_fetch: Whether we need to fetch from Jira/Confluence
        """
        logger.info(f"🔍 KG Agent preprocessing query: {message[:100]}...")
        
        result = {
            "relevant_entities": [],
            "suggested_action": None,
            "context": "",
            "needs_external_fetch": True,  # Default to fetching
            "confidence": 0.0
        }
        
        if not self.kg.enabled:
            logger.info("⚠️ Knowledge graph disabled, skipping preprocessing")
            return result
        
        message_lower = message.lower()
        
        # Extract potential issue keys from message
        import re
        issue_keys = re.findall(r'\b([A-Z]+-\d+)\b', message)
        
        # Check if entities exist in graph
        for issue_key in issue_keys:
            entity = self.kg.get_entity(issue_key)
            if entity:
                logger.info(f"✅ Found {issue_key} in knowledge graph")
                result["relevant_entities"].append(entity)
                result["confidence"] += 0.3
                
                # Get related entities
                related = self.kg.get_related_entities(issue_key, max_depth=2)
                result["relevant_entities"].extend(related)
                
                # Build context from cached data
                props = entity.get("properties", {})
                result["context"] += f"\nCached info for {issue_key}:\n"
                result["context"] += f"  Summary: {props.get('summary', 'N/A')}\n"
                result["context"] += f"  Status: {props.get('status', 'N/A')}\n"
                result["context"] += f"  Assignee: {props.get('assignee', 'N/A')}\n"
                
                # Check if data is fresh (less than 1 hour old)
                updated_at = entity.get("updated_at")
                if updated_at and self._is_recent(updated_at):
                    logger.info(f"📌 Data for {issue_key} is fresh, may skip external fetch")
                    result["needs_external_fetch"] = False
                    result["confidence"] += 0.3
        
        # Search for issues by keywords if no explicit keys found
        if not issue_keys and any(word in message_lower for word in ['issue', 'ticket', 'epic', 'story', 'bug']):
            logger.info("🔎 Searching KG for entities matching query keywords")
            
            # Search Jira issues in graph
            jira_entities = self.kg.search_entities(entity_type="jira_issue")
            
            # Simple keyword matching
            keywords = self._extract_keywords(message_lower)
            for entity in jira_entities:
                props = entity.get("properties", {})
                summary = props.get("summary", "").lower()
                
                # Check if any keyword matches
                if any(kw in summary for kw in keywords):
                    result["relevant_entities"].append(entity)
                    result["confidence"] += 0.1
                    logger.info(f"📍 Found matching issue in KG: {entity.get('id')}")
        
        # Analyze query intent
        if "child" in message_lower or "subtask" in message_lower:
            result["suggested_action"] = "get_child_issues"
            result["confidence"] += 0.2
        elif any(key in message_lower for key in ["search", "find", "show", "list"]):
            result["suggested_action"] = "search_jira"
            result["confidence"] += 0.2
        elif issue_keys:
            result["suggested_action"] = "get_jira_issue"
            result["confidence"] += 0.2
        
        # Determine if we have enough info from KG alone
        if result["confidence"] >= 0.6 and not result["needs_external_fetch"]:
            logger.info(f"✨ High confidence ({result['confidence']:.2f}) - KG can answer directly")
        else:
            logger.info(f"⚡ Lower confidence ({result['confidence']:.2f}) - need external fetch")
        
        return result
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Remove common stopwords
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                     'me', 'you', 'what', 'how', 'tell', 'show', 'find', 'get', 'about'}
        
        words = text.split()
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        return keywords[:5]  # Top 5 keywords
    
    def _is_recent(self, timestamp_str: str, max_age_hours: int = 1) -> bool:
        """Check if a timestamp is recent (less than max_age_hours old)"""
        try:
            from datetime import datetime, timedelta
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.utcnow()
            age = now - timestamp.replace(tzinfo=None)
            return age < timedelta(hours=max_age_hours)
        except Exception as e:
            logger.error(f"Error parsing timestamp: {e}")
            return False
    
    def get_entity_summary(self, entity_id: str) -> Optional[str]:
        """Get a text summary of an entity from the knowledge graph"""
        entity = self.kg.get_entity(entity_id)
        if not entity:
            return None
        
        props = entity.get("properties", {})
        entity_type = entity.get("type", "unknown")
        
        if entity_type == "jira_issue":
            return f"{entity_id}: {props.get('summary', 'N/A')} (Status: {props.get('status', 'N/A')})"
        elif entity_type == "confluence_page":
            return f"Page: {props.get('title', 'N/A')} in {props.get('space', 'N/A')}"
        elif entity_type == "user":
            return f"User: {props.get('name', 'N/A')}"
        
        return f"{entity_type}: {entity_id}"
    
    def get_related_context(self, entity_id: str) -> str:
        """Get contextual information about related entities"""
        related = self.kg.get_related_entities(entity_id, max_depth=1)
        
        if not related:
            return ""
        
        context = f"\nRelated entities for {entity_id}:\n"
        for rel_entity in related[:5]:  # Limit to top 5
            rel_type = rel_entity.get("relationship", "related")
            summary = self.get_entity_summary(rel_entity.get("id"))
            if summary:
                context += f"  - [{rel_type}] {summary}\n"
        
        return context


# Global KG agent instance
kg_agent = KnowledgeGraphAgent()
