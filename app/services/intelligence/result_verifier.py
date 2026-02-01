"""
Result Verifier - Verifies search results match user intent.
Follows Single Responsibility Principle.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ResultVerifier:
    """Verifies that search results match user's actual intent using LLM"""
    
    def __init__(self, llm):
        """
        Initialize with LLM for intelligent verification.
        
        Args:
            llm: LangChain LLM instance
        """
        self.llm = llm
    
    def verify_and_filter(
        self, 
        user_query: str, 
        results: List[Dict[str, Any]],
        skip_verification: bool = False,
        min_results_for_verification: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Verify that results match user's intent and filter out irrelevant items.
        
        Args:
            user_query: Original user question
            results: List of result dictionaries
            skip_verification: If True, skip verification (e.g., for child issues)
            min_results_for_verification: Only verify if results exceed this count
            
        Returns:
            Filtered list of relevant results
        """
        # Skip if explicitly requested
        if skip_verification:
            logger.info("⏭️ Skipping verification (results are inherently relevant)")
            return results
        
        # Skip if no results
        if not results:
            logger.info("⏭️ No results to verify")
            return results
        
        # If few results, probably already well-filtered
        if len(results) <= min_results_for_verification:
            logger.info(f"✅ Only {len(results)} results, skipping verification")
            return results
        
        try:
            logger.info(f"🔍 Verifying {len(results)} results match intent: '{user_query}'")
            
            # Create concise summary for LLM
            results_summary = []
            for i, result in enumerate(results[:20]):  # Limit to 20 to avoid token limits
                results_summary.append({
                    'index': i,
                    'key': result.get('key', 'N/A'),
                    'summary': result.get('summary', 'N/A')[:150],  # Truncate
                    'type': result.get('issue_type', 'N/A'),
                    'status': result.get('status', 'N/A')
                })
            
            # Ask LLM to verify
            verification_response = self._get_llm_verification(user_query, results_summary)
            
            # Parse LLM response
            filtered_results = self._parse_verification_response(
                verification_response, 
                results
            )
            
            logger.info(f"✅ Filtered from {len(results)} to {len(filtered_results)} relevant results")
            return filtered_results
            
        except Exception as e:
            logger.error(f"❌ Error verifying results: {e}", exc_info=True)
            # On error, return original results
            return results
    
    def _get_llm_verification(
        self, 
        user_query: str, 
        results_summary: List[Dict[str, Any]]
    ) -> str:
        """
        Get LLM to verify which results match intent.
        
        Args:
            user_query: Original user question
            results_summary: Summarized results for LLM
            
        Returns:
            LLM response text
        """
        verification_prompt = f"""User asked: "{user_query}"

Found {len(results_summary)} Jira issues. Determine which ones ACTUALLY match the user's intent.

Results:
{json.dumps(results_summary, indent=2)}

Task: Identify which issue indexes (0-{len(results_summary)-1}) are RELEVANT to the user's query.

ANALYSIS APPROACH:
1. **Understand Query Specificity:**
   - Specific queries (mentions particular topics, names, or detailed criteria) → Be strict, match precisely
   - General queries (broad terms like "all tasks", "recent work") → Be inclusive
   
2. **Keyword Matching:**
   - Match the ACTUAL subject matter, not just word forms
   - "climbing project" ≠ "software environment" even if both have "project/environment" 
   - Focus on what the issue is ABOUT, not just surface-level word matches

3. **Context Matters:**
   - If user asks about a topic (e.g., "books"), only include issues genuinely about that topic
   - Generic matches (e.g., issue is a "task" when user says "tasks") need topic relevance too
   - Status/type filters should be applied when explicitly mentioned

4. **Balance:**
   - Don't hallucinate connections, but don't over-filter valid results
   - If uncertain, lean toward including rather than excluding (user can refine)
   - Consider the issue summary/description content, not just metadata

Format your response as a comma-separated list of indexes:
RELEVANT: 0, 2, 5, 8

If ALL results are relevant, respond with:
RELEVANT: ALL

If NO results match, respond with:
RELEVANT: NONE"""
        
        response = self.llm.invoke(verification_prompt)
        return response.content.strip()
    
    def _parse_verification_response(
        self, 
        response_text: str, 
        original_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM verification response and filter results.
        
        Args:
            response_text: LLM response
            original_results: Original list of results
            
        Returns:
            Filtered results based on LLM verification
        """
        logger.info(f"🧠 LLM verification: {response_text}")
        
        # Check for ALL
        if "RELEVANT: ALL" in response_text:
            logger.info("✅ All results verified as relevant")
            return original_results
        
        # Check for NONE
        if "RELEVANT: NONE" in response_text:
            logger.warning("⚠️ No results matched user intent")
            return []
        
        # Extract relevant indexes
        relevant_match = re.search(r'RELEVANT:\s*([0-9,\s]+)', response_text)
        if relevant_match:
            indexes_str = relevant_match.group(1)
            relevant_indexes = [
                int(idx.strip()) 
                for idx in indexes_str.split(',') 
                if idx.strip().isdigit()
            ]
            
            # Filter to only relevant results
            filtered_results = [
                original_results[i] 
                for i in relevant_indexes 
                if i < len(original_results)
            ]
            
            return filtered_results
        
        # If parsing failed, return original
        logger.warning("⚠️ Could not parse verification response, returning all results")
        return original_results
    
    def verify_json_string(
        self, 
        user_query: str, 
        jira_results: str,
        skip_verification: bool = False
    ) -> str:
        """
        Verify results provided as JSON string (backward compatibility).
        
        Args:
            user_query: Original user question
            jira_results: JSON string of results
            skip_verification: If True, skip verification
            
        Returns:
            Filtered JSON string
        """
        try:
            # Parse JSON
            results = json.loads(jira_results) if isinstance(jira_results, str) else jira_results
            
            # Handle non-list results (error messages, etc.)
            if not results or not isinstance(results, list):
                return jira_results
            
            # Verify and filter
            filtered_results = self.verify_and_filter(
                user_query, 
                results, 
                skip_verification=skip_verification
            )
            
            # Return as JSON string
            return json.dumps(filtered_results, indent=2)
            
        except json.JSONDecodeError:
            # Not valid JSON, return as-is
            logger.warning("⚠️ Results are not valid JSON, returning unchanged")
            return jira_results
        except Exception as e:
            logger.error(f"❌ Error in verify_json_string: {e}")
            return jira_results
