"""
Agentic Planning and Iteration Service

Implements ReAct-style (Reason + Act) pattern where the AI:
1. Plans: Analyzes query and creates multi-step plan
2. Acts: Executes tools based on plan
3. Reflects: Evaluates results and decides next steps
4. Adapts: Adjusts plan based on findings or tries fallbacks

This enables intelligent, goal-driven tool use rather than rigid execution.
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class AgenticPlanner:
    """
    Intelligent planning and reflection service for agentic tool use.
    Uses LLM to plan, reflect, and adapt search strategies dynamically.
    """
    
    def __init__(self):
        self.llm = ChatOllama(
            model="llama3.1:8b",
            temperature=0.3,  # Lower temperature for more focused planning
            base_url="http://localhost:11434"
        )
        self.max_iterations = 3  # Safety limit for iteration loops
    
    async def create_search_plan(self, user_query: str, context: str = "", available_tools: List[str] = None) -> Dict[str, Any]:
        """
        Analyze query and create a multi-step search plan
        
        Returns:
            {
                "reasoning": "Why this plan makes sense",
                "steps": [
                    {"action": "search_jira", "reason": "...", "query": "..."},
                    {"action": "follow_links", "reason": "...", "criteria": "..."}
                ],
                "success_criteria": "What would constitute a complete answer",
                "fallback_strategy": "What to do if primary plan fails"
            }
        """
        if available_tools is None:
            available_tools = ["search_jira", "get_jira_issue", "search_web", "follow_web_links", "search_kg"]
        
        planning_prompt = f"""You are an intelligent search planning agent. Analyze the user's query and create a strategic plan.

User Query: {user_query}

{f"Context: {context}" if context else ""}

Available Tools:
- search_jira: Search Jira issues
- get_jira_issue: Get specific issue by key
- search_web: Search the web for information
- follow_web_links: Intelligently follow relevant links from web pages
- search_kg: Search knowledge graph for relationships

Create a strategic plan with these components:

1. REASONING: Why this approach makes sense for this query
2. STEPS: Ordered list of actions to take (2-4 steps max)
   - Each step should have: action, reason, and any parameters
3. SUCCESS_CRITERIA: How will you know when you have enough information?
4. FALLBACK_STRATEGY: What to try if primary approach doesn't yield results

IMPORTANT:
- Be efficient - prefer 2-3 focused steps over many scattered actions
- Consider whether web links might have deeper information (e.g., event details, competition info)
- Plan for the most likely path first, then fallbacks

Respond in this exact JSON format:
{{
    "reasoning": "Your analysis of the query and why this plan makes sense",
    "steps": [
        {{"action": "tool_name", "reason": "why this step", "query": "search terms or criteria"}},
        {{"action": "follow_web_links", "reason": "why follow links", "criteria": "what to look for in links"}}
    ],
    "success_criteria": "What constitutes a complete answer",
    "fallback_strategy": "What to try if this doesn't work"
}}"""
        
        try:
            logger.info("🧠 Creating search plan...")
            response = self.llm.invoke(planning_prompt)
            
            # Parse JSON response
            import json
            import re
            
            content = response.content
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            plan = json.loads(content)
            logger.info(f"✅ Plan created: {len(plan.get('steps', []))} steps")
            logger.info(f"📋 Reasoning: {plan.get('reasoning', '')[:100]}...")
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error creating plan: {e}")
            # Fallback: simple plan
            return {
                "reasoning": "Fallback to basic search",
                "steps": [{"action": "search_jira", "reason": "Primary search", "query": user_query}],
                "success_criteria": "Find relevant results",
                "fallback_strategy": "Try web search if Jira yields nothing"
            }
    
    async def reflect_on_results(
        self, 
        user_query: str, 
        step_executed: Dict[str, Any], 
        results: Any, 
        remaining_steps: List[Dict[str, Any]],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Reflect on results and decide next action
        
        Returns:
            {
                "assessment": "Quality of results (complete/partial/insufficient)",
                "has_answer": bool,
                "next_action": "continue/modify/stop",
                "reasoning": "Why this decision",
                "modification": Optional[Dict] - If modifying plan
            }
        """
        
        # Truncate results for LLM context
        results_summary = str(results)[:2000] if results else "No results"
        
        reflection_prompt = f"""You are evaluating search results to decide the next action.

Original Query: {user_query}

Step Executed: {step_executed.get('action')} - {step_executed.get('reason')}

Results Summary:
{results_summary}

Remaining Steps in Plan: {len(remaining_steps)}
Current Iteration: {iteration} / {self.max_iterations}

Assess the results and decide:

1. ASSESSMENT: Rate result quality
   - "complete": Query fully answered, no more searching needed
   - "partial": Some info found, but gaps remain
   - "insufficient": Results don't help answer query
   - "none": No results returned

2. HAS_ANSWER: Boolean - Do we have enough to answer the user's question?

3. NEXT_ACTION:
   - "stop": We have enough information
   - "continue": Proceed with next planned step
   - "modify": Adjust the plan based on findings
   - "fallback": Try alternative approach

4. REASONING: Explain your decision (2-3 sentences)

5. MODIFICATION (only if next_action is "modify"):
   - What to do differently
   - Why this change makes sense

Respond in JSON:
{{
    "assessment": "complete|partial|insufficient|none",
    "has_answer": true|false,
    "next_action": "stop|continue|modify|fallback",
    "reasoning": "Your explanation",
    "modification": {{"action": "...", "reason": "...", "query": "..."}}
}}"""
        
        try:
            logger.info(f"🤔 Reflecting on results (iteration {iteration})...")
            response = self.llm.invoke(reflection_prompt)
            
            import json
            import re
            
            content = response.content
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            reflection = json.loads(content)
            logger.info(f"✅ Reflection: {reflection.get('assessment')} → {reflection.get('next_action')}")
            logger.info(f"💭 {reflection.get('reasoning', '')[:150]}...")
            
            return reflection
            
        except Exception as e:
            logger.error(f"❌ Error in reflection: {e}")
            # Fallback: continue if we have remaining steps and haven't hit max iterations
            return {
                "assessment": "partial",
                "has_answer": False,
                "next_action": "continue" if (remaining_steps and iteration < self.max_iterations) else "stop",
                "reasoning": "Continuing with plan due to reflection error"
            }
    
    async def analyze_links(
        self, 
        user_query: str, 
        page_url: str,
        available_links: List[Dict[str, str]],
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Intelligently analyze links to decide which ones are worth following
        
        Args:
            user_query: Original user question
            page_url: URL of the page containing these links
            available_links: List of {"url": "...", "text": "link text"}
            context: Additional context about the search
        
        Returns:
            {
                "should_follow": bool,
                "selected_links": List[Dict] - Ranked links to follow
                "reasoning": "Why these links are relevant"
            }
        """
        
        if not available_links or len(available_links) == 0:
            return {
                "should_follow": False,
                "selected_links": [],
                "reasoning": "No links available"
            }
        
        # Format links for LLM
        links_text = "\n".join([
            f"{i+1}. {link.get('text', 'No text')} → {link.get('url', '')[:80]}"
            for i, link in enumerate(available_links[:10])  # Show max 10 links
        ])
        
        analysis_prompt = f"""You are analyzing web page links to determine which ones are worth following to answer the user's query.

User Query: {user_query}

Page: {page_url}

{f"Context: {context}" if context else ""}

Available Links:
{links_text}

Analyze these links and decide:

1. SHOULD_FOLLOW: Should we follow any of these links for more information?
   - Consider: Do these links likely contain details that would help answer the query?
   - Example: If query is about a competition, links with "schedule", "registration", "event details" are highly relevant

2. SELECTED_LINKS: Which links should we follow? (Rank top 1-2 most relevant)
   - Provide indices (1-based) of the links

3. REASONING: Why these links are relevant (or why none are worth following)

Respond in JSON:
{{
    "should_follow": true|false,
    "selected_indices": [1, 3],
    "reasoning": "Your explanation"
}}"""
        
        try:
            logger.info(f"🔗 Analyzing {len(available_links)} links...")
            response = self.llm.invoke(analysis_prompt)
            
            import json
            import re
            
            content = response.content
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            analysis = json.loads(content)
            
            # Convert indices to actual links
            selected_links = []
            if analysis.get("should_follow") and analysis.get("selected_indices"):
                for idx in analysis.get("selected_indices", []):
                    if 0 < idx <= len(available_links):
                        selected_links.append(available_links[idx - 1])
            
            logger.info(f"✅ Link analysis: Follow {len(selected_links)} links")
            if selected_links:
                logger.info(f"🎯 Selected: {[l.get('text', '')[:30] for l in selected_links]}")
            
            return {
                "should_follow": analysis.get("should_follow", False),
                "selected_links": selected_links,
                "reasoning": analysis.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing links: {e}")
            # Fallback: don't follow links on error
            return {
                "should_follow": False,
                "selected_links": [],
                "reasoning": "Error during link analysis"
            }


# Singleton instance
agentic_planner = AgenticPlanner()
