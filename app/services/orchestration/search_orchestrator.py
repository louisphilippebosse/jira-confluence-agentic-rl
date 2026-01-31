"""Search orchestration for intelligent, parallel, and agentic search operations"""
from typing import Dict, Any, List, Optional
import logging
import json
import asyncio
import re

from app.services.tools.jira.jira_service import jira_service
from app.services.tools.confluence.confluence_service import confluence_service
from app.services.tools.web.web_search_service import web_search_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
from app.services.intelligence.agentic_planner import agentic_planner
from app.services.core.thinking_stream import thinking_stream
from app.services.orchestration.mcp_operations import mcp_operations
from app.config import settings

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orchestrates all search operations: intelligent, parallel, and agentic"""
    
    def __init__(self, llm=None, skill_middleware=None):
        """Initialize search orchestrator with LLM and optional skill middleware for intelligent operations"""
        self.llm = llm
        self.skill_middleware = skill_middleware
    
    async def search_jira_issues(self, jql: str) -> str:
        """Search Jira issues using JQL and add to knowledge graph. Tries MCP first, falls back to direct API.
        
        Note: This method expects valid JQL. Use intelligent_jira_search() for natural language queries.
        """
        try:
            # Try MCP first
            results = await mcp_operations.search_jira_via_mcp(jql, max_results=20)
            
            # Fall back to direct API if MCP unavailable
            if results is None:
                results = jira_service.search_issues(jql, max_results=20)
            
            if not results:
                return "No issues found matching your query."
            
            # Add issues to knowledge graph
            for issue in results:
                knowledge_graph_service.add_jira_issue(issue)
            
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Jira search: {e}")
            return f"Error searching Jira: {str(e)}"
    
    async def intelligent_jira_search(self, message: str, query_analysis: Optional[Dict] = None) -> str:
        """Use LLM and skills to build intelligent JQL from natural language and try multiple search strategies.
        
        If skill_middleware is available, it uses the jql-optimizer skill for better query generation.
        Otherwise, falls back to direct LLM prompting.
        """
        try:
            primary_jql = None
            fallback_jql = None
            
            # SKILL-ENHANCED PATH: Use skill_middleware if available
            if self.skill_middleware:
                logger.info(f"🎯 [SKILL] Using jql-optimizer skill for: {message[:60]}...")
                
                try:
                    # First analyze the query if not already analyzed
                    if not query_analysis:
                        query_analysis = await self.skill_middleware.analyze_query(message)
                        logger.info(f"🔍 [SKILL] Query analysis: {query_analysis.get('intent', 'unknown')}")
                    
                    # Use skill to optimize JQL
                    optimized = await self.skill_middleware.optimize_jql(
                        message=message,
                        initial_jql=None,  # Let skill generate from scratch
                        analysis=query_analysis
                    )
                    
                    primary_jql = optimized.get('primary_jql')
                    fallback_jql = optimized.get('fallback_jql')
                    
                    # Validate the JQL from skills
                    if optimized.get('validation', {}).get('syntax_valid', False):
                        logger.info(f"✅ [SKILL] JQL validated: {primary_jql[:80]}...")
                    else:
                        logger.warning(f"⚠️ [SKILL] JQL may have issues, proceeding anyway")
                    
                    logger.info(f"🎯 [SKILL] PRIMARY: {primary_jql}")
                    logger.info(f"🎯 [SKILL] FALLBACK: {fallback_jql}")
                    
                except Exception as skill_error:
                    logger.warning(f"⚠️ [SKILL] Skill optimization failed: {skill_error}, falling back to direct LLM")
            
            # FALLBACK PATH: Direct LLM if no skills or skill failed
            if not primary_jql:
                logger.info(f"🧠 Using direct LLM for JQL generation...")
                
                prompt = f"""Analyze this user request and create Jira JQL queries.

User Request: "{message}"

Create 2 JQL queries:
1. PRIMARY - Specific query matching the request
2. FALLBACK - Broader query to catch more results

CRITICAL JQL RULES:
- ALWAYS quote multi-word status values: "To Do", "In Progress" (NOT To Do, In Progress)
- Use text~ for searching: text~"keyword"
- For "latest", "recent", "last updated": use ORDER BY updated DESC or updated >= -7d
- For time-based queries: updated >= -1d (last day), updated >= -7d (last week)
- Status values: "To Do", "In Progress", Done, Closed, Open
- Types: Epic, Story, Task, Bug
- When user asks for "latest" or "recent", sort by updated DESC and limit results
- For "my" tasks: use assignee=currentUser()

Format (respond in exactly this format):
PRIMARY: <jql query here>
FALLBACK: <jql query here>

Examples:
Request: "latest task updated"
PRIMARY: type=Task ORDER BY updated DESC
FALLBACK: ORDER BY updated DESC

Request: "my latest task"
PRIMARY: assignee=currentUser() AND type=Task ORDER BY updated DESC
FALLBACK: assignee=currentUser() ORDER BY updated DESC

Request: "tell me about my latest task updated"
PRIMARY: assignee=currentUser() ORDER BY updated DESC
FALLBACK: ORDER BY updated DESC

Request: "show me recent changes"
PRIMARY: updated >= -7d ORDER BY updated DESC
FALLBACK: updated >= -30d ORDER BY updated DESC

Request: "philosophy books to read"
PRIMARY: text~"philosophy" AND text~"book" AND status="To Do"
FALLBACK: text~"philosophy" AND text~"book"

Request: "show me open bugs"
PRIMARY: type=Bug AND status in (Open, "To Do", "In Progress")
FALLBACK: type=Bug

Request: "tasks in progress"
PRIMARY: type=Task AND status="In Progress"
FALLBACK: status="In Progress"

IMPORTANT: Output ONLY the two JQL queries, nothing else. No explanations.

Now create JQL for: "{message}"
PRIMARY:
FALLBACK:
"""

                response = self.llm.invoke(prompt)
                llm_output = response.content.strip()
                logger.info(f"🧠 LLM JQL response:\n{llm_output}")
                
                # Parse PRIMARY and FALLBACK queries
                primary_match = re.search(r'PRIMARY:\s*(.+?)(?=\n\s*FALLBACK:|\Z)', llm_output, re.IGNORECASE | re.DOTALL)
                fallback_match = re.search(r'FALLBACK:\s*(.+?)$', llm_output, re.IGNORECASE | re.DOTALL)
                
                primary_jql = primary_match.group(1).strip() if primary_match else None
                fallback_jql = fallback_match.group(1).strip() if fallback_match else None
            
            # Clean up JQL (works for both skill and direct LLM paths)
            def clean_jql(jql: str) -> str:
                if not jql:
                    return None
                # Remove markdown and backticks
                jql = re.sub(r'\*\*|\*|`', '', jql)
                # Take only first line if multiline
                jql = jql.split('\n')[0].strip()
                # Remove leading/trailing special chars
                jql = jql.strip('"\'` \n.;*')
                # Basic validation - must contain valid JQL operators
                valid_operators = ['=', '~', 'AND', 'OR', 'IN', 'NOT', 'ORDER']
                if not any(op in jql.upper() for op in valid_operators):
                    logger.warning(f"❌ Invalid JQL (no operators found): {jql}")
                    return None
                # Ensure quotes are balanced
                if jql.count('"') % 2 != 0:
                    jql += '"'
                return jql
            
            primary_jql = clean_jql(primary_jql)
            fallback_jql = clean_jql(fallback_jql)
            
            logger.info(f"🧠 FINAL PRIMARY JQL: {primary_jql}")
            logger.info(f"🧠 FINAL FALLBACK JQL: {fallback_jql}")
            
            # If all failed to generate queries, use a safe default
            if not primary_jql and not fallback_jql:
                logger.warning("⚠️ All JQL generation failed, using safe default")
                primary_jql = "ORDER BY updated DESC"
            
            # Try primary query first
            if primary_jql:
                try:
                    results = await mcp_operations.search_jira_via_mcp(primary_jql, max_results=20)
                    if results is None:
                        results = jira_service.search_issues(primary_jql, max_results=20)
                    if results and len(results) > 0:
                        logger.info(f"✅ Primary JQL found {len(results)} results")
                        for issue in results:
                            knowledge_graph_service.add_jira_issue(issue)
                        return json.dumps(results, indent=2)
                except Exception as jql_error:
                    logger.warning(f"⚠️ Primary JQL failed: {jql_error}")
            
            # Try fallback if primary didn't return results or failed
            if fallback_jql:
                try:
                    logger.info(f"🔄 Trying fallback JQL...")
                    results = await mcp_operations.search_jira_via_mcp(fallback_jql, max_results=20)
                    if results is None:
                        results = jira_service.search_issues(fallback_jql, max_results=20)
                    if results and len(results) > 0:
                        logger.info(f"✅ Fallback JQL found {len(results)} results")
                        for issue in results:
                            knowledge_graph_service.add_jira_issue(issue)
                        return json.dumps(results, indent=2)
                except Exception as jql_error:
                    logger.warning(f"⚠️ Fallback JQL failed: {jql_error}")
            
            # Last resort - use ORDER BY updated DESC
            logger.info("🔄 Both queries failed, using safe default ORDER BY updated DESC")
            try:
                results = jira_service.search_issues("ORDER BY updated DESC", max_results=10)
                if results:
                    for issue in results:
                        knowledge_graph_service.add_jira_issue(issue)
                    return json.dumps(results, indent=2)
            except Exception as e:
                logger.error(f"Default query also failed: {e}")
            
            return "No issues found matching your query."
            
        except Exception as e:
            logger.error(f"Error in intelligent Jira search: {e}", exc_info=True)
            return f"Error searching Jira: {str(e)}"
    
    async def get_jira_issue(self, issue_key: str) -> str:
        """Get detailed information about a specific Jira issue. Tries MCP first, falls back to direct API."""
        try:
            # Try MCP first
            result = await mcp_operations.get_jira_issue_via_mcp(issue_key.strip())
            
            # Fall back to direct API if MCP unavailable
            if result is None:
                result = jira_service.get_issue(issue_key.strip())
            
            if not result:
                return f"Issue {issue_key} not found."
            
            # Add to knowledge graph
            knowledge_graph_service.add_jira_issue(result)
            
            # Get related entities from knowledge graph
            related = knowledge_graph_service.get_related_entities(issue_key)
            if related:
                result["related_entities"] = related
            
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Jira issue: {e}")
            return f"Error getting issue: {str(e)}"
    
    def search_confluence(self, query: str) -> str:
        """Search Confluence documentation and add to knowledge graph"""
        try:
            logger.info(f"📚 Searching Confluence for: {query}")
            
            # Use personal space filter if configured
            space_key = settings.confluence_personal_space if settings.confluence_personal_space else None
            if space_key:
                logger.info(f"🔒 Filtering to personal space: {space_key}")
            
            # Fetch full content to extract relevant information
            results = confluence_service.search_content(query, limit=10, space_key=space_key, fetch_full_content=True)
            logger.info(f"✅ Found {len(results) if results else 0} Confluence pages")
            
            if not results:
                space_msg = f" in space {space_key}" if space_key else ""
                return f"No Confluence pages found matching your query{space_msg}."
            
            # Add pages to knowledge graph
            for page in results:
                knowledge_graph_service.add_confluence_page(page)
            
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Confluence search: {e}")
            return f"Error searching Confluence: {str(e)}"
    
    def get_confluence_page(self, page_id: str) -> str:
        """Get content from a specific Confluence page"""
        try:
            result = confluence_service.get_page(page_id.strip())
            if not result:
                return f"Page {page_id} not found."
            
            # Add to knowledge graph
            knowledge_graph_service.add_confluence_page(result)
            
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Confluence page: {e}")
            return f"Error getting page: {str(e)}"
    
    async def should_supplement_with_web(self, user_query: str, jira_results: List[Dict]) -> Dict[str, Any]:
        """
        Use LLM to intelligently determine if Jira results need web context supplement.
        
        Returns:
            {
                "should_search": bool,
                "search_query": str or None,
                "reason": str
            }
        """
        if not self.llm:
            return {"should_search": False, "search_query": None, "reason": "No LLM available"}
        
        try:
            if not jira_results or len(jira_results) == 0:
                return {"should_search": False, "search_query": None, "reason": "No results to analyze"}
            
            # Extract summaries and descriptions from top results
            context_snippets = []
            for result in jira_results[:3]:
                summary = result.get('summary', '')
                description = result.get('description', '')[:200] if result.get('description') else ''
                context_snippets.append(f"- {summary}: {description}")
            
            context_text = '\n'.join(context_snippets)
            
            prompt = f"""Analyze if these Jira results reference external events/venues that would benefit from web search context.

User Query: "{user_query}"

Jira Results:
{context_text}

ANALYZE:
1. Do the results mention external events, competitions, venues, or real-world activities?
2. Would web search provide useful additional context (dates, locations, details)?
3. Are there proper nouns (gym names, venue names, event names) worth searching?

Examples where web search HELPS:
- "CrossFit Prep" → Search for gym competition schedules
- "Marathon Training" → Search for upcoming marathon events
- "Conference Attendance" → Search for conference details
- "[Gym Name] Competition" → Search for venue and event info

Examples where web search DOESN'T HELP:
- "Fix login bug" → Internal technical work
- "Update documentation" → Internal task
- "Code review" → Development process
- "Sprint planning" → Internal meeting

Respond in JSON:
{{
    "should_search": true/false,
    "search_query": "focused search query" or null,
    "reason": "brief explanation"
}}

If should_search is true, extract key terms for a focused search query (gym names, event types, locations).
Keep it concise - return ONLY the JSON object."""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # Parse JSON response
            import re
            # Try to extract JSON from response
            if content.startswith('{'):
                decision = json.loads(content)
            else:
                # LLM might have wrapped it in markdown
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group())
                else:
                    logger.warning(f"⚠️ Failed to parse LLM decision: {content[:100]}")
                    return {"should_search": False, "search_query": None, "reason": "Failed to parse LLM response"}
            
            if decision.get("should_search"):
                logger.info(f"🌐 LLM recommends web search: {decision.get('reason')}")
                logger.info(f"🔍 Search query: {decision.get('search_query')}")
            else:
                logger.info(f"⏭️ LLM says no web search needed: {decision.get('reason')}")
            
            return decision
            
        except Exception as e:
            logger.error(f"❌ Error in web supplement analysis: {e}")
            return {"should_search": False, "search_query": None, "reason": f"Error: {str(e)}"}
    
    async def search_web(self, query: str) -> str:
        """Search the web and scrape actual page content"""
        try:
            logger.info(f"🌐 Searching web for: {query}")
            results = await web_search_service.search(query, max_results=5, scrape_content=True)
            if not results:
                return "No web results found for your query."
            
            # Format results with scraped content when available
            formatted_results = []
            for i, result in enumerate(results, 1):
                result_text = f"\n{i}. **{result.get('title', 'No title')}**"
                
                if result.get('url'):
                    result_text += f"\n   URL: {result['url']}"
                
                # Prioritize scraped content over snippet
                if result.get('scraped_content'):
                    content = result['scraped_content']
                    # Limit to first 800 chars if very long
                    if len(content) > 800:
                        content = content[:800] + "..."
                    result_text += f"\n   Content: {content}"
                elif result.get('snippet'):
                    result_text += f"\n   Snippet: {result['snippet']}"
                
                formatted_results.append(result_text)
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return f"Error searching web: {str(e)}"
    
    async def agentic_search(self, user_query: str, context: str = "", session_id: str = None, extract_issue_key_fn=None) -> Dict[str, Any]:
        """
        Intelligent agentic search with planning, execution, and reflection.
        
        This implements a ReAct-style pattern where the AI:
        1. Plans: Creates a multi-step search strategy
        2. Acts: Executes each step
        3. Reflects: Evaluates results and adapts
        4. Iterates: Continues until answer is found or max iterations reached
        
        Returns combined results with reasoning trace
        """
        logger.info(f"🤖 Starting AGENTIC search for: {user_query}")
        
        # Step 1: Create search plan
        await thinking_stream.simple_action("planning", "Analyzing query and creating strategy", session_id)
        
        plan = await agentic_planner.create_search_plan(
            user_query=user_query,
            context=context,
            available_tools=["search_jira", "get_jira_issue", "search_web", "follow_web_links", "search_kg"]
        )
        
        # Notify UI of plan
        await thinking_stream.plan_created(plan, session_id)
        
        logger.info(f"📋 Plan: {len(plan.get('steps', []))} steps")
        for i, step in enumerate(plan.get('steps', []), 1):
            logger.info(f"  Step {i}: {step.get('action')} - {step.get('reason')[:60]}...")
        
        # Initialize iteration state
        iteration = 0
        all_results = []
        reasoning_trace = [f"Initial Plan: {plan.get('reasoning')}"]
        remaining_steps = plan.get('steps', []).copy()
        
        # Step 2: Execute plan with reflection loop
        while iteration < agentic_planner.max_iterations and remaining_steps:
            iteration += 1
            step = remaining_steps.pop(0)
            
            logger.info(f"🔄 Iteration {iteration}: Executing {step.get('action')}")
            
            # Notify UI of step execution
            await thinking_stream.step_executing(step, iteration, session_id)
            
            # Execute step
            step_results = await self._execute_agentic_step(step, user_query, extract_issue_key_fn)
            all_results.append({
                "step": step,
                "results": step_results,
                "iteration": iteration
            })
            
            # Step 3: Reflect on results
            reflection = await agentic_planner.reflect_on_results(
                user_query=user_query,
                step_executed=step,
                results=step_results,
                remaining_steps=remaining_steps,
                iteration=iteration
            )
            
            # Notify UI of reflection
            await thinking_stream.reflection(reflection, iteration, session_id)
            
            reasoning_trace.append(
                f"Iteration {iteration}: {step.get('action')} → {reflection.get('assessment')} "
                f"({reflection.get('reasoning')})"
            )
            
            # Step 4: Decide next action based on reflection
            next_action = reflection.get('next_action', 'stop')
            
            if next_action == 'stop' or reflection.get('has_answer'):
                logger.info(f"✅ Stopping: {reflection.get('reasoning')}")
                reasoning_trace.append(f"Stopped: {reflection.get('reasoning')}")
                await thinking_stream.complete(iteration, session_id)
                break
            
            elif next_action == 'modify' and reflection.get('modification'):
                # Insert modified step at front of remaining steps
                modified_step = reflection.get('modification')
                remaining_steps.insert(0, modified_step)
                logger.info(f"🔧 Modified plan: {modified_step.get('action')}")
                reasoning_trace.append(f"Modified plan: {modified_step.get('reason')}")
                await thinking_stream.adapting(modified_step, session_id)
            
            elif next_action == 'fallback':
                # Try fallback strategy
                logger.info(f"🔀 Trying fallback: {plan.get('fallback_strategy')}")
                reasoning_trace.append(f"Fallback: {plan.get('fallback_strategy')}")
                # Add fallback as next step (simplified - could be more sophisticated)
                if 'web' not in str([s.get('action') for s in all_results]):
                    fallback_step = {
                        "action": "search_web",
                        "reason": "Fallback to web search",
                        "query": user_query
                    }
                    remaining_steps.insert(0, fallback_step)
                    await thinking_stream.adapting(fallback_step, session_id)
            
            elif next_action == 'continue':
                logger.info(f"➡️ Continuing with plan ({len(remaining_steps)} steps left)")
                # Just continue to next step
            
            # Safety: Don't go beyond max iterations
            if iteration >= agentic_planner.max_iterations:
                logger.warning(f"⚠️ Reached max iterations ({agentic_planner.max_iterations})")
                reasoning_trace.append("Reached max iterations limit")
                break
        
        # Return combined results with reasoning trace
        logger.info(f"🎉 Agentic search complete: {iteration} iterations, {len(all_results)} steps executed")
        
        return {
            "results": all_results,
            "reasoning_trace": reasoning_trace,
            "plan": plan,
            "iterations": iteration
        }
    
    async def _execute_agentic_step(self, step: Dict[str, Any], user_query: str, extract_issue_key_fn=None) -> Any:
        """Execute a single step from the agentic plan"""
        action = step.get('action')
        query = step.get('query', user_query)
        
        # Import here to avoid circular dependency
        from app.services.knowledge.kg_query_service import KGQueryService
        kg_service = KGQueryService(self.llm)
        
        try:
            if action == 'search_jira':
                # Use intelligent JQL conversion for natural language queries
                return await self.intelligent_jira_search(query)
            
            elif action == 'get_jira_issue':
                issue_key = step.get('issue_key')
                if not issue_key and extract_issue_key_fn:
                    issue_key = extract_issue_key_fn(query)
                if issue_key:
                    return await self.get_jira_issue(issue_key)
                return "No issue key provided"
            
            elif action == 'search_web':
                return await self.search_web(query)
            
            elif action == 'follow_web_links':
                # This requires previous web results with links
                # For now, do a web search and intelligently follow links
                web_results = await web_search_service.search(query, max_results=3, scrape_content=True)
                
                if web_results and len(web_results) > 0:
                    first_result = web_results[0]
                    
                    # Check if we got related links from scraping
                    if first_result.get('scraped_content') and 'related_links' in str(first_result):
                        # Get links from the scraped result (if our scraper returned them)
                        logger.info("🔗 Analyzing links from web results...")
                        # The scraper already followed relevant links, return those results
                        return first_result.get('scraped_content', '')
                
                return web_results
            
            elif action == 'search_kg':
                return kg_service.search_knowledge_graph_direct(query)
            
            else:
                logger.warning(f"Unknown action: {action}")
                return f"Unknown action: {action}"
                
        except Exception as e:
            logger.error(f"Error executing step {action}: {e}")
            return f"Error: {str(e)}"
    
    async def parallel_multi_source_search(self, query: str) -> Dict[str, any]:
        """
        Search multiple sources in parallel (Jira, Confluence, Knowledge Graph)
        and return combined results for the LLM to analyze
        """
        logger.info(f"🔄 Starting parallel multi-source search for: {query}")
        
        # Import here to avoid circular dependency
        from app.services.knowledge.kg_query_service import KGQueryService
        kg_service = KGQueryService(self.llm)
        
        # Define async tasks for each source
        async def search_jira_async():
            try:
                logger.info(f"🎯 [PARALLEL] Searching Jira...")
                # Use intelligent JQL conversion instead of raw query
                result = await self.intelligent_jira_search(query)
                return {"source": "jira", "data": result, "success": True}
            except Exception as e:
                logger.error(f"❌ [PARALLEL] Jira search failed: {e}")
                return {"source": "jira", "data": None, "success": False, "error": str(e)}
        
        async def search_confluence_async():
            try:
                logger.info(f"📚 [PARALLEL] Searching Confluence...")
                # Run sync function in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.search_confluence, query)
                return {"source": "confluence", "data": result, "success": True}
            except Exception as e:
                logger.error(f"❌ [PARALLEL] Confluence search failed: {e}")
                return {"source": "confluence", "data": None, "success": False, "error": str(e)}
        
        async def search_kg_async():
            try:
                logger.info(f"🕸️ [PARALLEL] Searching Knowledge Graph...")
                # KG search is sync, run in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, kg_service.search_knowledge_graph_direct, query)
                return {"source": "knowledge_graph", "data": result, "success": True}
            except Exception as e:
                logger.error(f"❌ [PARALLEL] KG search failed: {e}")
                return {"source": "knowledge_graph", "data": None, "success": False, "error": str(e)}
        
        # Execute all searches in parallel
        results = await asyncio.gather(
            search_jira_async(),
            search_confluence_async(),
            search_kg_async(),
            return_exceptions=True
        )
        
        # Organize results by source
        combined = {
            "jira": None,
            "confluence": None,
            "knowledge_graph": None,
            "successful_sources": []
        }
        
        for result in results:
            if isinstance(result, dict) and result.get("success"):
                source = result["source"]
                combined[source] = result["data"]
                combined["successful_sources"].append(source)
                logger.info(f"✅ [PARALLEL] {source} search completed successfully")
        
        logger.info(f"🎉 Parallel search complete. Successful sources: {combined['successful_sources']}")
        return combined
