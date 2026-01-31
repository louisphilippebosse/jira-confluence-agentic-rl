"""
Entity Extractor Service - Extracts entities and relationships from text using LLM.
Implements Graph RAG approach for knowledge graph enrichment.
"""
import re
import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents an extracted entity"""
    name: str
    entity_type: str
    description: str


@dataclass
class Relationship:
    """Represents a relationship between entities"""
    source: str
    target: str
    relation: str
    description: str


class EntityExtractorService:
    """Extracts entities and relationships from text using LLM prompts"""
    
    # System prompt for entity extraction
    EXTRACTION_PROMPT = """
-Goal-
Given a text document, identify all entities and their entity types from the text and all relationships among the identified entities.
Extract up to {max_entities} entity-relation triplets.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: Type of the entity (PERSON, PROJECT, ISSUE, FEATURE, BUG, TASK, CONCEPT, TECHNOLOGY, TEAM, MILESTONE)
- entity_description: Comprehensive description of the entity's attributes and activities

Format each entity as:
entity_name: <name>
entity_type: <type>
entity_description: <description>

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity
- target_entity: name of the target entity
- relation: relationship between source_entity and target_entity (WORKS_ON, DEPENDS_ON, BLOCKS, RELATED_TO, ASSIGNED_TO, PART_OF, IMPLEMENTS, FIXES)
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other

Format each relationship as:
source_entity: <source>
target_entity: <target>
relation: <relation>
relationship_description: <description>

-Real Data-
######################
text: {text}
######################
output:"""
    
    def __init__(self, llm):
        """
        Initialize with LLM for entity extraction.
        
        Args:
            llm: LangChain LLM instance
        """
        self.llm = llm
    
    def _parse_extraction_response(self, response: str) -> Tuple[List[Entity], List[Relationship]]:
        """
        Parse LLM response to extract entities and relationships.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Tuple of (entities, relationships)
        """
        entities = []
        relationships = []
        
        # Patterns for extraction
        entity_pattern = r'entity_name:\s*(.+?)\s*entity_type:\s*(.+?)\s*entity_description:\s*(.+?)(?=\n\n|\nentity_name:|\nsource_entity:|$)'
        relationship_pattern = r'source_entity:\s*(.+?)\s*target_entity:\s*(.+?)\s*relation:\s*(.+?)\s*relationship_description:\s*(.+?)(?=\n\n|\nsource_entity:|\nentity_name:|$)'
        
        # Extract entities
        for match in re.finditer(entity_pattern, response, re.DOTALL):
            name = match.group(1).strip()
            entity_type = match.group(2).strip()
            description = match.group(3).strip()
            
            if name and entity_type:
                entities.append(Entity(
                    name=name,
                    entity_type=entity_type,
                    description=description
                ))
        
        # Extract relationships
        for match in re.finditer(relationship_pattern, response, re.DOTALL):
            source = match.group(1).strip()
            target = match.group(2).strip()
            relation = match.group(3).strip()
            description = match.group(4).strip()
            
            if source and target and relation:
                relationships.append(Relationship(
                    source=source,
                    target=target,
                    relation=relation,
                    description=description
                ))
        
        logger.info(f"✅ Extracted {len(entities)} entities and {len(relationships)} relationships")
        return entities, relationships
    
    def extract_from_text(self, text: str, max_entities: int = 10) -> Tuple[List[Entity], List[Relationship]]:
        """
        Extract entities and relationships from text.
        
        Args:
            text: Text to analyze
            max_entities: Maximum number of entities to extract
            
        Returns:
            Tuple of (entities, relationships)
        """
        try:
            # Truncate very long text
            if len(text) > 4000:
                text = text[:4000] + "..."
                logger.warning(f"⚠️ Text truncated to 4000 chars for extraction")
            
            # Generate prompt
            prompt = self.EXTRACTION_PROMPT.format(
                text=text,
                max_entities=max_entities
            )
            
            # Call LLM
            response = self.llm.invoke(prompt)
            response_text = response.content.strip()
            
            # Parse response
            entities, relationships = self._parse_extraction_response(response_text)
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"❌ Entity extraction failed: {e}")
            return [], []
    
    def extract_from_jira_issue(self, issue: Dict[str, Any]) -> Tuple[List[Entity], List[Relationship]]:
        """
        Extract entities from a Jira issue.
        
        Args:
            issue: Jira issue dictionary
            
        Returns:
            Tuple of (entities, relationships)
        """
        # Build text from issue
        text_parts = []
        
        if issue.get('summary'):
            text_parts.append(f"Title: {issue['summary']}")
        
        if issue.get('description'):
            text_parts.append(f"Description: {issue['description']}")
        
        # Add comments if available
        if issue.get('comments'):
            comments_text = " ".join([c.get('body', '') for c in issue['comments'][:3]])  # First 3 comments
            if comments_text:
                text_parts.append(f"Comments: {comments_text}")
        
        text = "\n\n".join(text_parts)
        
        if not text:
            return [], []
        
        logger.info(f"🔍 Extracting entities from issue {issue.get('key', 'unknown')}")
        return self.extract_from_text(text, max_entities=8)
    
    def extract_from_confluence_page(self, page: Dict[str, Any]) -> Tuple[List[Entity], List[Relationship]]:
        """
        Extract entities from a Confluence page.
        
        Args:
            page: Confluence page dictionary
            
        Returns:
            Tuple of (entities, relationships)
        """
        # Build text from page
        text_parts = []
        
        if page.get('title'):
            text_parts.append(f"Title: {page['title']}")
        
        if page.get('body'):
            # Strip HTML tags from body
            body = re.sub(r'<[^>]+>', ' ', page['body'])
            text_parts.append(f"Content: {body}")
        
        text = "\n\n".join(text_parts)
        
        if not text:
            return [], []
        
        logger.info(f"🔍 Extracting entities from Confluence page {page.get('id', 'unknown')}")
        return self.extract_from_text(text, max_entities=10)
