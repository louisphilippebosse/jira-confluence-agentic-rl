"""
Skill Middleware - Intelligence layer that enhances existing services

This wraps proven services (JiraQueryBuilder, ResultVerifier, KG)
with LLM-powered intelligence without replacing them.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from langchain_community.chat_models import ChatOllama

logger = logging.getLogger(__name__)


class SkillMiddleware:
    """
    Middleware layer that enhances existing services with skill intelligence.
    
    Unlike the parallel orchestrator, this wraps and improves existing logic.
    """
    
    def __init__(
        self,
        llm,
        query_analyzer=None,
        jql_builder=None,
        result_verifier=None,
        kg_service=None
    ):
        self.llm = llm
        self.query_analyzer = query_analyzer
        self.jql_builder = jql_builder
        self.result_verifier = result_verifier
        self.kg_service = kg_service
        
        logger.info("🎯 Initialized SkillMiddleware - wrapping existing services")
    
    @classmethod
    def create(cls, llm) -> "SkillMiddleware":
        """
        Factory method to create SkillMiddleware with all dependencies.
        
        This encapsulates all the service-specific imports so the orchestrator
        doesn't need to know about Jira, Confluence, etc.
        """
        try:
            from app.services.intelligence.query_analyzer_service import QueryAnalyzerService
            from app.services.tools.jira.jira_query_builder import JiraQueryBuilder
            from app.services.intelligence.result_verifier import ResultVerifier
            from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
            
            return cls(
                llm=llm,
                query_analyzer=QueryAnalyzerService(),  # No LLM needed
                jql_builder=JiraQueryBuilder(llm),
                result_verifier=ResultVerifier(llm),
                kg_service=knowledge_graph_service
            )
        except Exception as e:
            logger.error(f"Failed to create SkillMiddleware: {e}", exc_info=True)
            raise
    
    async def analyze_query(self, message: str, conversation_history: Optional[List] = None) -> Dict[str, Any]:
        """
        SKILL: query-analyzer
        
        Enhances existing query analysis with LLM-powered intent understanding.
        
        Wraps: QueryAnalyzerService
        """
        try:
            logger.info(f"🔍 [query-analyzer] Analyzing: {message[:100]}")
            
            # Build context from history
            history_context = ""
            if conversation_history:
                recent = conversation_history[-5:]
                history_context = "\n".join([f"{m.role}: {m.content[:100]}" for m in recent])
            
            prompt = f"""Analyze this user query to extract structured intent.

User query: "{message}"

Recent conversation:
{history_context}

IMPORTANT: 
- If query is simple (like "more information", "details"), keep it simple
- If query asks about relationships/links, mark as relationship_query
- For relationship queries like "link between X and Y", set data_sources to ["jira", "knowledge_graph"]

Extract:
1. **Intent**: What does the user want? (search_jira/get_issue/search_confluence/analyze_metrics/relationship_query/general_question)
2. **Entities**: Issue keys (PROJ-123), project names, people, keywords, issue types (Epic/Idea/Delivery)
3. **Data Sources**: Which sources needed? (jira/confluence/knowledge_graph/web)
   - For relationship queries: ALWAYS include ["jira", "knowledge_graph"]
   - For external events/competitions: include "web"
4. **Time Context**: Any time-based filter? (latest/recent/last_week/specific_date)
5. **Relationships**: Asking about relationships? (link_between/related_to/delivered_by/blocks/depends_on)

For simple follow-up questions:
{{
    "intent": "get_issue",
    "entities": {{"keywords": []}},
    "data_sources": ["jira"],
    "time_context": {{"type": null, "window": null}},
    "relationship_query": {{"type": null, "entities": []}},
    "confidence": 0.9
}}

For relationship queries like "link between Gymnastics and Forever Athlete":
{{
    "intent": "relationship_query",
    "entities": {{
        "keywords": ["Gymnastics", "Forever Athlete"],
        "issue_types": ["Epic", "Idea"]
    }},
    "data_sources": ["jira", "knowledge_graph"],
    "time_context": {{"type": null, "window": null}},
    "relationship_query": {{
        "type": "link_between",
        "entities": ["Gymnastics Skill Development", "The Forever Athlete"]
    }},
    "confidence": 0.85
}}

Otherwise respond in JSON:
{{
    "intent": "<intent-type>",
    "entities": {{
        "issue_keys": [],
        "projects": [],
        "people": [],
        "keywords": [],
        "issue_types": []
    }},
    "data_sources": [],
    "time_context": {{"type": null, "window": null}},
    "relationship_query": {{"type": null, "entities": []}},
    "confidence": 0.0
}}
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # Parse JSON from response
            json_match = content
            if "```json" in content:
                json_match = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_match = content.split("```")[1].split("```")[0].strip()
            
            # Handle case where LLM returns non-JSON response
            if not json_match or not json_match.startswith('{'):
                logger.warning(f"⚠️ [query-analyzer] LLM returned non-JSON: {content[:100]}")
                raise ValueError("Non-JSON response from LLM")
            
            analysis = json.loads(json_match)
            
            # Enhance with existing analyzer methods
            analysis["has_issue_key"] = bool(self.query_analyzer.extract_single_issue_key(message))
            analysis["is_child_query"] = self.query_analyzer.is_asking_for_children(message)
            
            logger.info(f"✅ [query-analyzer] Intent: {analysis['intent']}, Confidence: {analysis.get('confidence', 0)}")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ [query-analyzer] Failed: {e}")
            # Fallback to basic analysis
            return {
                "intent": "search_jira",
                "entities": {"keywords": message.split()[:5]},
                "data_sources": ["jira"],
                "confidence": 0.5
            }
    
    async def optimize_jql(
        self,
        message: str,
        initial_jql: Optional[str] = None,
        analysis: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        SKILL: jql-optimizer
        
        Enhances JQL queries from JiraQueryBuilder with validation and fallbacks.
        
        Wraps: JiraQueryBuilder
        """
        try:
            logger.info(f"🔧 [jql-optimizer] Optimizing JQL for: {message[:100]}")
            
            # If no initial JQL provided, build one using existing builder
            if not initial_jql:
                initial_jql = self.jql_builder.build_jql_from_keywords(message)
            
            prompt = f"""Optimize this JQL query to be more reliable and effective.

Original query: "{message}"
Initial JQL: {initial_jql}

Analysis context: {json.dumps(analysis or {}, indent=2)}

Create:
1. **Primary JQL**: Optimized query with proper quoting and filters
2. **Fallback JQL**: Broader query in case primary returns nothing

CRITICAL RULES:
- Quote multi-word status values: "In Progress", "To Do"
- Use text~ for keyword searches: text~"keyword"
- Add ORDER BY updated DESC for "latest/recent" queries
- Validate syntax (balanced quotes, valid operators)

Respond in JSON:
{{
    "primary_jql": "<optimized-jql>",
    "fallback_jql": "<broader-jql>",
    "validation": {{
        "syntax_valid": true,
        "estimated_results": "10-50"
    }},
    "strategy": "description"
}}
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # Parse JSON
            json_match = content
            if "```json" in content:
                json_match = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_match = content.split("```")[1].split("```")[0].strip()
            
            optimized = json.loads(json_match)
            
            logger.info(f"✅ [jql-optimizer] Primary: {optimized['primary_jql'][:100]}")
            return optimized
            
        except Exception as e:
            logger.error(f"❌ [jql-optimizer] Failed: {e}")
            # Fallback to original JQL
            return {
                "primary_jql": initial_jql or "",
                "fallback_jql": "ORDER BY updated DESC",
                "validation": {"syntax_valid": False}
            }
    
    async def rank_results(
        self,
        message: str,
        results: str,  # JSON string of results
        analysis: Optional[Dict] = None,
        skip_verification: bool = False
    ) -> Dict[str, Any]:
        """
        SKILL: result-ranker
        
        Enhances result verification with relevance scoring and ranking.
        
        Wraps: ResultVerifier
        """
        try:
            logger.info(f"📊 [result-ranker] Ranking {len(results)} characters of results")
            
            # First use existing verifier to filter
            filtered_json = self.result_verifier.verify_json_string(
                message,
                results,
                skip_verification=skip_verification
            )
            
            # Parse to add scoring
            try:
                filtered_data = json.loads(filtered_json)
            except:
                filtered_data = []
            
            if not filtered_data:
                return {
                    "ranked_results": [],
                    "filtered_out": 0,
                    "grouping": {}
                }
            
            # Add relevance scoring via LLM
            prompt = f"""Score these results for relevance to the user's query.

Query: "{message}"
Results: {json.dumps(filtered_data[:10], indent=2)[:2000]}  # Limit context

For each result, assign a relevance score (0-1) based on:
- Keyword matches in summary/description
- Status relevance (Open/In Progress > Done for active queries)
- Recency (updated recently scores higher)

Respond with JSON array:
[
    {{"index": 0, "relevance_score": 0.95, "reasons": ["Exact keyword match", "Recent update"]}},
    ...
]
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # Parse scores
            json_match = content
            if "```json" in content:
                json_match = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_match = content.split("```")[1].split("```")[0].strip()
            
            try:
                scores = json.loads(json_match)
                
                # Apply scores to results
                ranked = []
                for item in scores:
                    if item["index"] < len(filtered_data):
                        result = filtered_data[item["index"]].copy()
                        result["_relevance_score"] = item["relevance_score"]
                        result["_reasons"] = item.get("reasons", [])
                        ranked.append(result)
                
                # Sort by score
                ranked.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)
                
                logger.info(f"✅ [result-ranker] Ranked {len(ranked)} results")
                return {
                    "ranked_results": ranked,
                    "filtered_out": len(filtered_data) - len(ranked),
                    "grouping": {}
                }
            except:
                # If scoring fails, return filtered results as-is
                return {
                    "ranked_results": filtered_data,
                    "filtered_out": 0,
                    "grouping": {}
                }
            
        except Exception as e:
            logger.error(f"❌ [result-ranker] Failed: {e}")
            # Fallback to basic verification
            filtered = self.result_verifier.verify_json_string(message, results, skip_verification)
            try:
                return {
                    "ranked_results": json.loads(filtered),
                    "filtered_out": 0,
                    "grouping": {}
                }
            except:
                return {"ranked_results": [], "filtered_out": 0, "grouping": {}}
    
    async def enrich_with_kg(
        self,
        message: str,
        results: List[Dict],
        analysis: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        SKILL: kg-enricher
        
        Enriches results with Knowledge Graph context and relationships.
        
        Wraps: KnowledgeGraphService
        """
        try:
            logger.info(f"🕸️ [kg-enricher] Enriching {len(results)} results")
            
            # Get KG insights using existing methods
            kg_context = self.kg_service.get_community_for_query(message, self.llm) if hasattr(self.kg_service, 'get_community_for_query') else []
            central_entities = self.kg_service.get_central_entities(limit=5)
            
            # Enrich each result
            enriched = []
            for result in results:
                enriched_result = result.copy()
                
                # Find related entities in KG
                issue_key = result.get("key") or result.get("id")
                if issue_key:
                    related = self.kg_service.get_related_entities(issue_key)
                    enriched_result["_kg_context"] = {
                        "related_entities": related[:5] if related else [],
                        "in_graph": bool(related)
                    }
                
                enriched.append(enriched_result)
            
            # Build global context
            global_context = {
                "relevant_communities": [{"name": c[1], "score": c[2]} for c in (kg_context or [])[:3]],
                "central_entities": [{"id": e[0], "score": e[1]} for e in (central_entities or [])],
                "total_related": len(enriched)
            }
            
            logger.info(f"✅ [kg-enricher] Added context from {len(kg_context or [])} communities")
            return {
                "enriched_results": enriched,
                "global_context": global_context
            }
            
        except Exception as e:
            logger.error(f"❌ [kg-enricher] Failed: {e}")
            # Return results without enrichment
            return {
                "enriched_results": results,
                "global_context": {}
            }
    
    async def semantic_rerank(
        self,
        message: str,
        results: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """
        SKILL: semantic-ranker
        
        Re-ranks search results using semantic similarity from Knowledge Graph.
        
        This uses the KG's semantic search to find the best matches and
        boosts results that appear in both the Jira search and KG.
        
        Args:
            message: Original query
            results: Jira/Confluence results to re-rank
            top_k: Number of results to return
            
        Returns:
            Re-ranked results with semantic scores
        """
        try:
            if not results:
                return []
            
            logger.info(f"🎯 [semantic-ranker] Re-ranking {len(results)} results")
            
            # Get semantic matches from Knowledge Graph
            kg_matches = self.kg_service.semantic_search(message, limit=20)
            kg_match_ids = {m["id"]: m["score"] for m in kg_matches}
            
            # Score each result
            ranked = []
            for i, result in enumerate(results):
                result_copy = result.copy()
                issue_key = result.get("key") or result.get("id", "")
                
                # Base score from position (earlier = higher)
                base_score = 1.0 - (i / len(results)) * 0.5
                
                # Boost if found in KG semantic search
                kg_boost = kg_match_ids.get(issue_key, 0) * 0.5
                
                # Final score
                final_score = base_score + kg_boost
                result_copy["_semantic_score"] = final_score
                result_copy["_kg_match"] = issue_key in kg_match_ids
                
                ranked.append(result_copy)
            
            # Sort by semantic score
            ranked.sort(key=lambda x: x.get("_semantic_score", 0), reverse=True)
            
            logger.info(f"✅ [semantic-ranker] Re-ranked {len(ranked)} results, KG matches: {sum(1 for r in ranked if r.get('_kg_match'))}")
            return ranked[:top_k]
            
        except Exception as e:
            logger.error(f"❌ [semantic-ranker] Failed: {e}")
            return results[:top_k]

    async def graphrag_query(
        self,
        message: str,
        mode: str = "local",
        only_context: bool = False
    ) -> Dict[str, Any]:
        """
        SKILL: nano-graphrag
        
        Uses nano-graphrag for unified Graph + Vector RAG queries.
        
        This provides two search modes:
        - local: Entity-focused (finds specific issues, relationships)
        - global: Community-focused (finds themes, patterns across data)
        
        Args:
            message: User query
            mode: "local" or "global"
            only_context: If True, returns only retrieved context without LLM response
            
        Returns:
            Dict with response and metadata
        """
        try:
            from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
            
            if not nano_graphrag_service.enabled:
                logger.warning("⚠️ [nano-graphrag] Service is disabled")
                return {
                    "response": None,
                    "mode": mode,
                    "error": "nano-graphrag is disabled",
                    "fallback_available": True
                }
            
            logger.info(f"🧠 [nano-graphrag] Query: {message[:100]}... (mode={mode})")
            
            # Execute GraphRAG query
            response = nano_graphrag_service.query(
                query=message,
                mode=mode,
                only_context=only_context
            )
            
            logger.info(f"✅ [nano-graphrag] Got response ({len(response)} chars)")
            
            return {
                "response": response,
                "mode": mode,
                "query": message,
                "only_context": only_context
            }
            
        except Exception as e:
            logger.error(f"❌ [nano-graphrag] Failed: {e}")
            return {
                "response": None,
                "mode": mode,
                "error": str(e),
                "fallback_available": True
            }

    async def enhance_with_graphrag(
        self,
        message: str,
        jira_results: List[Dict] = None,
        confluence_results: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        SKILL: graphrag-enhanced-response
        
        Enhances tool results with nano-graphrag context for better responses.
        
        This method:
        1. Gets relevant context from nano-graphrag (local mode for entities)
        2. Combines with Jira/Confluence results
        3. Returns unified context for response synthesis
        
        Args:
            message: User query
            jira_results: Results from Jira search
            confluence_results: Results from Confluence search
            
        Returns:
            Enhanced context dict
        """
        try:
            from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
            
            if not nano_graphrag_service.enabled:
                return {
                    "graphrag_context": None,
                    "jira_results": jira_results or [],
                    "confluence_results": confluence_results or [],
                    "enhanced": False
                }
            
            logger.info(f"🎯 [graphrag-enhanced] Enhancing response for: {message[:80]}...")
            
            # Get local context (entity-focused) for specific information
            local_context = nano_graphrag_service.query(
                query=message,
                mode="local",
                only_context=True  # Just get the context, not full LLM response
            )
            
            logger.info(f"✅ [graphrag-enhanced] Got {len(local_context) if local_context else 0} chars of context")
            
            return {
                "graphrag_context": local_context,
                "jira_results": jira_results or [],
                "confluence_results": confluence_results or [],
                "enhanced": True,
                "mode": "local"
            }
            
        except Exception as e:
            logger.error(f"❌ [graphrag-enhanced] Failed: {e}")
            return {
                "graphrag_context": None,
                "jira_results": jira_results or [],
                "confluence_results": confluence_results or [],
                "enhanced": False,
                "error": str(e)
            }
