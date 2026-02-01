"""
Skill Orchestrator - Executes skills with reasoning and adaptation

This is the "brain" that:
1. Selects relevant skills for a query
2. Executes them in the right order
3. Evaluates results and adapts strategy if needed
4. Synthesizes final answer
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.services.core.skill_registry import Skill, get_skill_registry
from app.services.tools.jira.jira_service import JiraService
from app.services.tools.confluence.confluence_service import ConfluenceService
from app.services.graphrag.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Result from executing a skill"""
    skill_name: str
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class SkillOrchestrator:
    """
    Orchestrates skill execution with multi-step reasoning.
    
    This replaces the hardcoded if/else routing with dynamic skill discovery.
    """
    
    def __init__(
        self,
        llm,
        jira_service: JiraService,
        confluence_service: ConfluenceService,
        kg_service: KnowledgeGraphService
    ):
        self.llm = llm
        self.jira_service = jira_service
        self.confluence_service = confluence_service
        self.kg_service = kg_service
        self.registry = get_skill_registry()
        
        logger.info(f"🎯 Orchestrator loaded with {len(self.registry.skills)} skills")
    
    async def execute_query(self, query: str, context: Optional[Dict] = None) -> Dict:
        """
        Main entry point - execute a user query using skills.
        
        This is the replacement for ai_agent_service.generate_response()
        """
        logger.info(f"🔍 Orchestrating query: {query}")
        
        # Respect user's explicit context selection
        context_modes = context.get('context_modes', []) if context else []
        if context_modes:
            logger.info(f"👤 Respecting user context selection: {context_modes}")
        
        # Step 1: Discover relevant skills
        relevant_skills = self.registry.find_relevant_skills(query, self.llm)
        
        # Filter skills based on context_modes if provided
        if context_modes:
            filtered_skills = []
            for skill in relevant_skills:
                if 'jira' in context_modes and 'jira' in skill.name:
                    filtered_skills.append(skill)
                elif 'confluence' in context_modes and 'confluence' in skill.name:
                    filtered_skills.append(skill)
                elif 'knowledge-graph' in context_modes and 'knowledge-graph' in skill.name:
                    filtered_skills.append(skill)
            relevant_skills = filtered_skills
            logger.info(f"🎯 Filtered to {len(relevant_skills)} skills based on context")
        
        if not relevant_skills:
            return {
                "answer": "I don't have the appropriate skills to answer that question.",
                "sources": [],
                "reasoning": "No matching skills found"
            }
        
        # Step 2: Execute skills in order
        results = []
        for skill in relevant_skills:
            logger.info(f"⚙️ Executing skill: {skill.name}")
            result = await self._execute_skill(skill, query, context, results)
            results.append(result)
        
        # Step 3: Evaluate and adapt if needed
        needs_retry = self._evaluate_results(results, query)
        if needs_retry:
            logger.info("🔄 Results insufficient, adapting strategy...")
            # Could implement retry logic here
        
        # Step 4: Synthesize final answer
        return await self._synthesize_answer(query, results, relevant_skills)
    
    async def _execute_skill(
        self,
        skill: Skill,
        query: str,
        context: Optional[Dict],
        previous_results: List[SkillResult]
    ) -> SkillResult:
        """Execute a single skill"""
        try:
            # Build context for this skill
            skill_context = {
                "query": query,
                "instructions": skill.instructions,
                "previous_results": [
                    {"skill": r.skill_name, "data": r.data}
                    for r in previous_results if r.success
                ],
                **(context or {})
            }
            
            # Route to appropriate handler based on skill name
            if skill.name == "jira-search":
                data = await self._execute_jira_search(query, skill_context)
            elif skill.name == "knowledge-graph-query":
                data = await self._execute_kg_query(query, skill_context)
            elif skill.name == "confluence-search":
                data = await self._execute_confluence_search(query, skill_context)
            else:
                raise NotImplementedError(f"Skill '{skill.name}' not implemented yet")
            
            return SkillResult(
                skill_name=skill.name,
                success=True,
                data=data,
                metadata={"query": query}
            )
            
        except Exception as e:
            logger.error(f"❌ Skill {skill.name} failed: {e}")
            return SkillResult(
                skill_name=skill.name,
                success=False,
                data=None,
                error=str(e)
            )
    
    async def _execute_jira_search(self, query: str, context: Dict) -> Dict:
        """Execute Jira search skill"""
        instructions = context["instructions"]
        
        # Use LLM to determine search strategy
        strategy_prompt = f"""Using this skill:

{instructions}

User query: "{query}"

Choose the best strategy (direct-keys/llm-jql/keyword-extraction) and provide the search parameters.

Respond in this format:
STRATEGY: <strategy-name>
PARAMS: <parameters>

Example:
STRATEGY: llm-jql
PARAMS: Find issues assigned to John Doe in the last month
"""
        
        response = self.llm.invoke(strategy_prompt)
        strategy_text = response.content.strip()
        
        # Parse strategy
        lines = strategy_text.split('\n')
        strategy = None
        params = None
        
        for line in lines:
            if line.startswith('STRATEGY:'):
                strategy = line.split(':', 1)[1].strip()
            elif line.startswith('PARAMS:'):
                params = line.split(':', 1)[1].strip()
        
        logger.info(f"📋 Jira strategy: {strategy}")
        
        # Execute based on strategy
        if strategy == "direct-keys":
            # Extract keys from params
            keys = [k.strip() for k in params.split(',') if k.strip()]
            issues = []
            for key in keys:
                issue = await self.jira_service.get_issue(key)
                if issue:
                    issues.append(issue)
            return {"strategy": "direct-keys", "issues": issues}
        
        elif strategy == "llm-jql":
            # Use existing JQL builder
            from app.services.tools.jira.jira_query_builder import JiraQueryBuilder
            jql_builder = JiraQueryBuilder(self.llm)
            jql = jql_builder.build_jql(params)
            
            if jql:
                issues = await self.jira_service.search_issues(jql)
                return {"strategy": "llm-jql", "jql": jql, "issues": issues}
        
        elif strategy == "keyword-extraction":
            # Fallback to keyword search
            issues = await self.jira_service.search_issues_by_keywords(params)
            return {"strategy": "keyword-extraction", "issues": issues}
        
        return {"strategy": "none", "issues": []}
    
    async def _execute_kg_query(self, query: str, context: Dict) -> Dict:
        """Execute Knowledge Graph query skill"""
        # Use LLM to extract entities and determine entity type
        extract_prompt = f"""Extract entities from this query: "{query}"

Entity types available: jira_issues, confluence_pages, people, projects, concepts

Respond with:
ENTITIES: <comma-separated list>
TYPE: <entity-type>
"""
        
        response = self.llm.invoke(extract_prompt)
        result_text = response.content.strip()
        
        entities = []
        entity_type = None
        
        for line in result_text.split('\n'):
            if line.startswith('ENTITIES:'):
                entities = [e.strip() for e in line.split(':', 1)[1].split(',')]
            elif line.startswith('TYPE:'):
                entity_type = line.split(':', 1)[1].strip()
        
        # Query KG
        kg_results = self.kg_service.find_related_entities(
            entities,
            entity_type_filter=entity_type
        )
        
        return {
            "entities": entities,
            "entity_type": entity_type,
            "results": kg_results
        }
    
    async def _execute_confluence_search(self, query: str, context: Dict) -> Dict:
        """Execute Confluence search skill"""
        # Extract keywords
        keywords = self._extract_keywords(query)
        
        # Search Confluence using correct method name
        results = self.confluence_service.search_content(
            query=" ".join(keywords),
            limit=5
        )
        
        return {
            "keywords": keywords,
            "pages": results
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Simple keyword extraction"""
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for'}
        words = text.lower().split()
        return [w for w in words if w not in stop_words and len(w) > 2][:5]
    
    def _evaluate_results(self, results: List[SkillResult], query: str) -> bool:
        """
        Evaluate if results are sufficient or if we need to adapt.
        Returns True if we should retry with different approach.
        """
        # Check if any skills succeeded
        successful = [r for r in results if r.success]
        
        if not successful:
            logger.warning("⚠️ No skills succeeded")
            return True
        
        # Check if we got any data
        has_data = any(
            r.data and (
                (isinstance(r.data, dict) and r.data) or
                (isinstance(r.data, list) and len(r.data) > 0)
            )
            for r in successful
        )
        
        if not has_data:
            logger.warning("⚠️ No data returned from skills")
            return True
        
        return False
    
    async def _synthesize_answer(
        self,
        query: str,
        results: List[SkillResult],
        skills: List[Skill]
    ) -> Dict:
        """Synthesize final answer from skill results"""
        
        # Collect all successful data
        all_data = []
        sources = []
        
        for result in results:
            if result.success and result.data:
                all_data.append({
                    "skill": result.skill_name,
                    "data": result.data
                })
                sources.append(result.skill_name)
        
        # CRITICAL: If no data found, don't hallucinate - admit we found nothing
        if not all_data:
            return {
                "answer": "I couldn't find any information about that in your Jira, Confluence, or Knowledge Graph. The search returned no results.",
                "sources": [],
                "skill_results": [],
                "reasoning": "No data found from any source"
            }
        
        # Use LLM to synthesize answer
        synthesis_prompt = f"""User query: "{query}"

Data from skills:
{all_data}

CRITICAL RULES:
- Base your answer ONLY on the data provided above
- DO NOT add external knowledge or make up information
- If the data doesn't answer the question, say so
- Be direct and factual

Synthesize an answer that:
1. Directly addresses the user's question using ONLY the provided data
2. Combines information from all sources
3. Is clear and concise
4. Does NOT add external context or general knowledge

Answer:"""
        
        response = self.llm.invoke(synthesis_prompt)
        answer = response.content.strip()
        
        return {
            "answer": answer,
            "sources": sources,
            "skill_results": all_data,
            "reasoning": f"Searched: {', '.join(s.name for s in skills)}"
        }
