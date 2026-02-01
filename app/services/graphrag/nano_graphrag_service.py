"""
Nano-GraphRAG Service - Unified Graph + Vector RAG using nano-graphrag.

This service provides:
1. Automatic entity extraction from Jira/Confluence content
2. Graph-based relationships (community detection built-in)
3. Vector embeddings for semantic search
4. Both LOCAL (entity-focused) and GLOBAL (community-focused) search modes

Uses Ollama for both LLM and embeddings.
"""
import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
import numpy as np

import ollama
from nano_graphrag import GraphRAG, QueryParam
from nano_graphrag.base import BaseKVStorage
from nano_graphrag._utils import compute_args_hash, wrap_embedding_func_with_attrs

from app.config import settings

logger = logging.getLogger(__name__)

# Configure nano-graphrag logging
logging.getLogger("nano-graphrag").setLevel(logging.INFO)


def repair_json(json_str: str) -> dict:
    """
    Attempt to repair and parse malformed JSON from LLM responses.
    Handles common issues like trailing commas, missing quotes, etc.
    """
    if not json_str:
        return {}
    
    # Try direct parse first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', json_str)
    if json_match:
        json_str = json_match.group(1).strip()
    
    # Common repairs
    repairs = [
        # Remove trailing commas before } or ]
        (r',(\s*[}\]])', r'\1'),
        # Fix unquoted keys
        (r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":'),
        # Replace single quotes with double quotes (careful with apostrophes)
        (r"(?<!\\)'([^']*)'(?=\s*[,:}\]])", r'"\1"'),
        # Remove control characters
        (r'[\x00-\x1f]+', ' '),
        # Fix missing comma between objects
        (r'\}\s*\{', '},{'),
    ]
    
    repaired = json_str
    for pattern, replacement in repairs:
        repaired = re.sub(pattern, replacement, repaired)
    
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    
    # Last resort: try to extract just the essential fields for community reports
    try:
        # Look for title and summary patterns
        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', json_str)
        summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', json_str)
        findings_match = re.search(r'"findings"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
        
        result = {
            "title": title_match.group(1) if title_match else "Community Report",
            "summary": summary_match.group(1) if summary_match else "Unable to parse summary",
            "findings": []
        }
        
        if findings_match:
            # Try to extract finding strings
            finding_strs = re.findall(r'"([^"]+)"', findings_match.group(1))
            result["findings"] = finding_strs[:5]  # Limit to 5 findings
        
        logger.warning(f"Used fallback JSON extraction, got: {result.get('title', 'unknown')}")
        return result
    except Exception:
        pass
    
    # Ultimate fallback
    logger.error(f"Could not repair JSON: {json_str[:200]}...")
    return {
        "title": "Parse Error",
        "summary": "Failed to parse LLM response",
        "findings": []
    }


def _patched_convert_response_to_json(response: str) -> dict:
    """Patched version of nano-graphrag's convert_response_to_json with better error handling"""
    return repair_json(response)


# Monkey-patch nano-graphrag's JSON parser at MULTIPLE levels to ensure it takes effect
# The _op module imports the function directly, so we need to patch there too
try:
    import nano_graphrag._utils as nano_utils
    import nano_graphrag._op as nano_op
    
    # Patch the utils module
    nano_utils.convert_response_to_json = _patched_convert_response_to_json
    
    # Patch the _op module's reference (this is the one actually used)
    if hasattr(nano_op, 'use_string_json_convert_func'):
        # It's assigned to a variable, we need to find where it's used
        pass
    
    # The function is used as a default parameter, so we need to patch at module level
    nano_op.convert_response_to_json = _patched_convert_response_to_json
    
    # Also patch it in the global namespace of _op if it imported it directly
    if 'convert_response_to_json' in dir(nano_op):
        setattr(nano_op, 'convert_response_to_json', _patched_convert_response_to_json)
    
    logger.info("✅ Patched nano-graphrag JSON parser with robust error handling")
except Exception as e:
    logger.warning(f"Could not patch nano-graphrag JSON parser: {e}")


class NanoGraphRAGService:
    """
    Wrapper around nano-graphrag that integrates with Jira/Confluence data.
    
    Uses Ollama for:
    - LLM: Entity extraction, community summaries, query response
    - Embeddings: nomic-embed-text for vector search
    """
    
    # Default embedding model settings (can be overridden via config)
    DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
    DEFAULT_EMBEDDING_DIM = 768
    DEFAULT_EMBEDDING_MAX_TOKENS = 8192
    
    def __init__(self, working_dir: str = None):
        self.working_dir = working_dir or settings.nano_graphrag_working_dir
        self.llm_model = settings.ollama_model  # e.g., "llama3.2:latest"
        self.ollama_base_url = settings.ollama_base_url
        self.enabled = settings.enable_nano_graphrag
        
        # Use config embedding model if set, otherwise default
        self.EMBEDDING_MODEL = getattr(settings, 'ollama_embedding_model', self.DEFAULT_EMBEDDING_MODEL)
        self.EMBEDDING_MODEL_DIM = self.DEFAULT_EMBEDDING_DIM
        self.EMBEDDING_MODEL_MAX_TOKENS = self.DEFAULT_EMBEDDING_MAX_TOKENS
        
        self._rag: Optional[GraphRAG] = None
        self._initialized = False
        
        # Ensure working directory exists
        os.makedirs(self.working_dir, exist_ok=True)
        logger.info(f"NanoGraphRAG service initialized with working_dir={self.working_dir}")
    
    @property
    def rag(self) -> GraphRAG:
        """Lazy-load the GraphRAG instance"""
        if not self.enabled:
            raise RuntimeError("NanoGraphRAG is disabled. Set ENABLE_NANO_GRAPHRAG=true in .env")
        
        if self._rag is None:
            self._rag = GraphRAG(
                working_dir=self.working_dir,
                enable_llm_cache=True,
                best_model_func=self._ollama_model_func,
                cheap_model_func=self._ollama_model_func,
                embedding_func=self._ollama_embedding_func(),
                # Use our robust JSON parser that handles malformed LLM responses
                convert_response_to_json_func=repair_json,
            )
            self._initialized = True
            logger.info("GraphRAG instance created with robust JSON parser")
        return self._rag
    
    async def _ollama_model_func(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: List[Dict] = [],
        **kwargs
    ) -> str:
        """
        Ollama LLM function with caching support.
        Used for entity extraction, community summaries, and query responses.
        """
        # Remove kwargs not supported by Ollama
        kwargs.pop("max_tokens", None)
        kwargs.pop("response_format", None)
        
        ollama_client = ollama.AsyncClient(host=self.ollama_base_url)
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Handle caching
        hashing_kv: BaseKVStorage = kwargs.pop("hashing_kv", None)
        messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        
        if hashing_kv is not None:
            args_hash = compute_args_hash(self.llm_model, messages)
            cached_response = await hashing_kv.get_by_id(args_hash)
            if cached_response is not None:
                return cached_response["return"]
        
        # Call Ollama
        try:
            response = await ollama_client.chat(
                model=self.llm_model,
                messages=messages,
                **kwargs
            )
            result = response["message"]["content"]
            
            # Cache the response
            if hashing_kv is not None:
                await hashing_kv.upsert({
                    args_hash: {"return": result, "model": self.llm_model}
                })
            
            return result
        except Exception as e:
            logger.error(f"Ollama LLM error: {e}")
            raise
    
    def _ollama_embedding_func(self):
        """Create the Ollama embedding function with proper attributes"""
        
        @wrap_embedding_func_with_attrs(
            embedding_dim=self.EMBEDDING_MODEL_DIM,
            max_token_size=self.EMBEDDING_MODEL_MAX_TOKENS,
        )
        async def ollama_embedding(texts: List[str]) -> np.ndarray:
            """Generate embeddings using Ollama's nomic-embed-text model"""
            embeddings = []
            for text in texts:
                try:
                    data = ollama.embeddings(
                        model=self.EMBEDDING_MODEL,
                        prompt=text
                    )
                    embeddings.append(data["embedding"])
                except Exception as e:
                    logger.error(f"Embedding error for text: {e}")
                    # Return zero vector on error
                    embeddings.append([0.0] * self.EMBEDDING_MODEL_DIM)
            return embeddings
        
        return ollama_embedding
    
    # =========================================================================
    # Fast Vector Indexing (No LLM Entity Extraction)
    # =========================================================================
    
    def index_entities_fast(
        self,
        entities: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Index entities using ONLY vector embeddings - no LLM entity extraction.
        
        This is the HYBRID approach:
        - Graph structure comes from NetworkX (explicit relationships)
        - Semantic search comes from embeddings (implicit similarity)
        
        ~100x faster than full insert() because it skips LLM parsing.
        
        Args:
            entities: List of dicts with 'id', 'type', 'text' fields
            progress_callback: Optional fn(current, total) for progress updates
            
        Returns:
            Stats dict with counts
        """
        if not entities:
            return {"indexed": 0}
        
        logger.info(f"⚡ Fast-indexing {len(entities)} entities (embeddings only, no LLM)...")
        
        indexed = 0
        batch_size = 10  # Embed in small batches
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            
            for entity in batch:
                try:
                    entity_id = entity.get('id', '')
                    entity_type = entity.get('type', 'unknown')
                    text = entity.get('text', '')
                    
                    if not text:
                        continue
                    
                    # Generate embedding directly (no LLM parsing)
                    embedding = ollama.embeddings(
                        model=self.EMBEDDING_MODEL,
                        prompt=text[:2000]  # Truncate long texts
                    )["embedding"]
                    
                    # Store in the vector database
                    # nano-graphrag uses vdb_entities for entity embeddings
                    if hasattr(self.rag, 'entities_vdb') and self.rag.entities_vdb:
                        asyncio.get_event_loop().run_until_complete(
                            self.rag.entities_vdb.upsert({
                                entity_id: {
                                    "embedding": embedding,
                                    "entity_type": entity_type,
                                    "content": text[:500],  # Store summary
                                }
                            })
                        )
                    
                    indexed += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to index {entity.get('id', '?')}: {e}")
            
            # Progress update
            if progress_callback:
                progress_callback(i + len(batch), len(entities))
        
        logger.info(f"✅ Fast-indexed {indexed}/{len(entities)} entities")
        return {"indexed": indexed, "total": len(entities)}
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for semantically similar entities using embeddings.
        
        This works even without LLM entity extraction - just needs indexed embeddings.
        
        Args:
            query: Natural language search query
            top_k: Number of results to return
            entity_types: Optional filter by entity type
            
        Returns:
            List of matching entities with scores
        """
        try:
            # Get query embedding
            query_embedding = ollama.embeddings(
                model=self.EMBEDDING_MODEL,
                prompt=query
            )["embedding"]
            
            # Search the vector database
            if hasattr(self.rag, 'entities_vdb') and self.rag.entities_vdb:
                results = asyncio.get_event_loop().run_until_complete(
                    self.rag.entities_vdb.query(
                        query_embedding,
                        top_k=top_k * 2  # Get more, then filter
                    )
                )
                
                # Filter by entity type if specified
                if entity_types and results:
                    results = [
                        r for r in results
                        if r.get("entity_type") in entity_types
                    ]
                
                return results[:top_k]
            
            return []
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def insert(self, text: str) -> None:
        """
        Insert text into the graph RAG.
        nano-graphrag automatically:
        - Chunks the text
        - Extracts entities and relationships
        - Builds the graph
        - Creates embeddings
        - Detects communities and generates summaries
        """
        logger.info(f"Inserting text ({len(text)} chars) into GraphRAG...")
        self.rag.insert(text)
        logger.info("Insert complete!")
    
    def entity_exists(self, entity_name: str) -> bool:
        """
        Check if an entity with the given name exists in the graph.
        Uses case-insensitive matching.
        """
        if not self._rag:
            return False
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            # Access the underlying NetworkX graph
            if hasattr(graph_storage, '_graph'):
                graph = graph_storage._graph
            elif hasattr(graph_storage, 'graph'):
                graph = graph_storage.graph
            else:
                # Can't access graph, assume not exists to allow insertion
                return False
            
            # Check if entity exists (case-insensitive)
            entity_lower = entity_name.lower()
            for node in graph.nodes():
                if node.lower() == entity_lower or entity_lower in node.lower():
                    return True
            return False
        except Exception as e:
            logger.debug(f"Could not check entity existence: {e}")
            return False
    
    def insert_batch(self, texts: List[str]) -> None:
        """Insert multiple texts in batch"""
        logger.info(f"Batch inserting {len(texts)} texts...")
        self.rag.insert(texts)
        logger.info("Batch insert complete!")
    
    async def ainsert(self, text: str) -> None:
        """Async version of insert"""
        logger.info(f"Async inserting text ({len(text)} chars)...")
        await self.rag.ainsert(text)
        logger.info("Async insert complete!")
    
    async def ainsert_batch(self, texts: List[str]) -> None:
        """Async batch insert"""
        logger.info(f"Async batch inserting {len(texts)} texts...")
        await self.rag.ainsert(texts)
        logger.info("Async batch insert complete!")
    
    def query(
        self,
        query: str,
        mode: str = "local",
        only_context: bool = False
    ) -> str:
        """
        Query the graph RAG.
        
        Args:
            query: The question to ask
            mode: "local" (entity-focused) or "global" (community-focused)
            only_context: If True, return only the retrieved context without LLM response
            
        Returns:
            The LLM response (or context if only_context=True)
        """
        param = QueryParam(
            mode=mode,
            only_need_context=only_context
        )
        return self.rag.query(query, param=param)
    
    async def aquery(
        self,
        query: str,
        mode: str = "local",
        only_context: bool = False
    ) -> str:
        """Async version of query"""
        param = QueryParam(
            mode=mode,
            only_need_context=only_context
        )
        return await self.rag.aquery(query, param=param)
    
    def insert_jira_issue(self, issue: Dict[str, Any]) -> None:
        """
        Convert a Jira issue to text and insert into GraphRAG.
        nano-graphrag will automatically extract entities.
        
        Skips insertion if the issue is already in the graph (checks by key).
        """
        key = issue.get("key", "UNKNOWN")
        
        # Check if this issue already exists in the graph
        if self.entity_exists(key):
            logger.debug(f"Issue {key} already exists in GraphRAG, skipping insert")
            return
        
        # Build rich text representation of the issue
        summary = issue.get("summary", "No summary")
        description = issue.get("description", "") or ""
        issue_type = issue.get("issue_type", "Issue")
        status = issue.get("status", "Unknown")
        project = issue.get("project", "Unknown")
        assignee = issue.get("assignee", "Unassigned")
        labels = ", ".join(issue.get("labels", []))
        components = ", ".join(issue.get("components", []))
        
        # Build structured text that nano-graphrag can parse
        text = f"""
Jira Issue: {key}
Type: {issue_type}
Project: {project}
Status: {status}
Assignee: {assignee}
Labels: {labels}
Components: {components}

Summary: {summary}

Description:
{description}
"""
        
        # Add parent info if available
        if issue.get("parent"):
            parent_key = issue["parent"].get("key")
            parent_summary = issue["parent"].get("summary", "")
            text += f"\nParent Issue: {parent_key} - {parent_summary}\n"
        
        # Add subtasks
        subtasks = issue.get("subtasks", [])
        if subtasks:
            text += "\nSubtasks:\n"
            for st in subtasks:
                st_key = st.get("key", "")
                st_summary = st.get("summary", "")
                text += f"- {st_key}: {st_summary}\n"
        
        # Add linked issues
        links = issue.get("issue_links", [])
        if links:
            text += "\nLinked Issues:\n"
            for link in links:
                link_key = link.get("key", "")
                link_type = link.get("type", "relates to")
                link_summary = link.get("summary", "")
                text += f"- {link_type}: {link_key} - {link_summary}\n"
        
        logger.info(f"Inserting new Jira issue: {key}")
        self.insert(text.strip())
    
    def insert_confluence_page(self, page: Dict[str, Any]) -> None:
        """
        Convert a Confluence page to text and insert into GraphRAG.
        Skips insertion if the page already exists (checks by title).
        """
        title = page.get("title", "Untitled")
        
        # Check if this page already exists in the graph
        if self.entity_exists(title):
            logger.debug(f"Page '{title}' already exists in GraphRAG, skipping insert")
            return
        
        space = page.get("space", "Unknown")
        content = page.get("content", "") or ""
        page_type = page.get("type", "page")
        
        # Build structured text
        text = f"""
Confluence Page: {title}
Space: {space}
Type: {page_type}

Content:
{content}
"""
        
        # Add labels
        labels = page.get("labels", [])
        if labels:
            text += f"\nLabels: {', '.join(labels)}\n"
        
        logger.info(f"Inserting Confluence page: {title}")
        self.insert(text.strip())
    
    def clear(self) -> None:
        """Clear all data from the GraphRAG working directory"""
        import shutil
        
        files_to_remove = [
            "vdb_entities.json",
            "kv_store_full_docs.json",
            "kv_store_text_chunks.json",
            "kv_store_community_reports.json",
            "graph_chunk_entity_relation.graphml",
            "llm_response_cache.json"
        ]
        
        for filename in files_to_remove:
            filepath = os.path.join(self.working_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Removed {filepath}")
        
        # Reset the RAG instance
        self._rag = None
        self._initialized = False
        logger.info("GraphRAG cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the current GraphRAG state"""
        stats = {
            "working_dir": self.working_dir,
            "llm_model": self.llm_model,
            "embedding_model": self.EMBEDDING_MODEL,
            "enabled": self.enabled,
            "initialized": self._initialized,
        }
        
        # Check for existing data files
        graphml_path = os.path.join(self.working_dir, "graph_chunk_entity_relation.graphml")
        if os.path.exists(graphml_path):
            stats["has_graph"] = True
            stats["graph_file_size_mb"] = os.path.getsize(graphml_path) / (1024 * 1024)
            
            # Try to parse graphml for entity/relation counts
            try:
                import networkx as nx
                g = nx.read_graphml(graphml_path)
                stats["graph_nodes"] = g.number_of_nodes()
                stats["graph_edges"] = g.number_of_edges()
            except Exception:
                pass
        else:
            stats["has_graph"] = False
        
        # Check other data files
        data_files = [
            ("vdb_entities.json", "has_vector_db"),
            ("kv_store_full_docs.json", "has_docs"),
            ("kv_store_text_chunks.json", "has_chunks"),
            ("kv_store_community_reports.json", "has_communities"),
        ]
        
        for filename, key in data_files:
            filepath = os.path.join(self.working_dir, filename)
            stats[key] = os.path.exists(filepath)
        
        return stats
    
    def populate_from_jira_confluence(
        self,
        jira_issues: List[Dict[str, Any]],
        confluence_pages: List[Dict[str, Any]] = []
    ) -> Dict[str, int]:
        """
        Bulk populate from Jira and Confluence data.
        
        This builds text representations and inserts them in batch
        for efficient processing by nano-graphrag.
        """
        texts = []
        
        # Convert Jira issues to text
        for issue in jira_issues:
            key = issue.get("key", "UNKNOWN")
            summary = issue.get("summary", "No summary")
            description = issue.get("description", "") or ""
            issue_type = issue.get("issue_type", "Issue")
            status = issue.get("status", "Unknown")
            project = issue.get("project", "Unknown")
            assignee = issue.get("assignee", "Unassigned")
            labels = ", ".join(issue.get("labels", []))
            
            text = f"Jira Issue {key} ({issue_type}) in project {project}: {summary}. "
            text += f"Status: {status}. Assignee: {assignee}. "
            if labels:
                text += f"Labels: {labels}. "
            if description:
                text += f"Description: {description[:1000]}"
            
            # Add parent relationship (handle both string and dict formats)
            parent = issue.get("parent")
            if parent:
                if isinstance(parent, dict):
                    parent_key = parent.get("key", "")
                else:
                    parent_key = str(parent)
                if parent_key:
                    text += f" This issue is a child of {parent_key}."
            
            # Add linked issues as text
            for link in issue.get("issue_links", []):
                link_key = link.get("key", "")
                link_type = link.get("type", "relates to")
                text += f" {key} {link_type} {link_key}."
            
            texts.append(text.strip())
        
        # Convert Confluence pages to text
        for page in confluence_pages:
            title = page.get("title", "Untitled")
            space = page.get("space", "Unknown")
            content = page.get("content", "") or ""
            
            text = f"Confluence page '{title}' in space {space}. "
            text += content[:2000]  # Limit content size
            
            texts.append(text.strip())
        
        # Batch insert all texts
        logger.info(f"Inserting {len(texts)} documents into nano-graphrag...")
        if texts:
            self.insert_batch(texts)
        
        return {
            "jira_issues": len(jira_issues),
            "confluence_pages": len(confluence_pages),
            "total_documents": len(texts)
        }


# Singleton instance
nano_graphrag_service = NanoGraphRAGService()
