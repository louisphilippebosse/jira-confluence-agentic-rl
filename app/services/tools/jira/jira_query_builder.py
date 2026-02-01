"""
Jira Query Builder - Builds JQL queries from natural language.

This module was moved from intelligence/ to tools/jira/ for better
semantic organization. All Jira-related code is now in one place.
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class JiraQueryBuilder:
    """Builds JQL (Jira Query Language) queries from natural language"""
    
    def __init__(self, llm):
        """
        Initialize with LLM for intelligent query generation.
        
        Args:
            llm: LangChain LLM instance
        """
        self.llm = llm
    
    def build_jql_from_keywords(self, message: str) -> str:
        """
        Build JQL query from message using keyword extraction.
        Extracts meaningful nouns/topics, ignores question words.
        
        Args:
            message: User's natural language query
            
        Returns:
            JQL query string
        """
        message_lower = message.lower()
        
        # Expanded stop words - exclude ALL question/filler words
        stop_words = {
            # Articles & prepositions
            'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'from', 'by',
            # Question words
            'show', 'me', 'find', 'get', 'list', 'all', 'my', 'tell', 'do', 'does',
            'what', 'which', 'how', 'when', 'where', 'who', 'why', 'would', 'could', 'should',
            'can', 'know', 'anything', 'something', 'any', 'some',
            # Meta words about issues
            'issues', 'issue', 'task', 'tasks', 'ticket', 'tickets', 'item', 'items',
            # Time/status descriptors (these are better handled by JQL directly)
            'about', 'latest', 'recent', 'last', 'new', 'updated', 'changed',
            # Auxiliaries
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'that', 'this', 'these', 'those', 'or', 'and', 'but', 'if', 'then',
            'i', 'you', 'we', 'they', 'it', 'created'
        }
        
        words = re.findall(r'\b\w+\b', message_lower)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        if not keywords:
            logger.info("No specific keywords, returning recent items")
            return 'order by updated DESC'
        
        # Use only the most meaningful keywords (likely nouns/topics)
        # If too many keywords, take first 3 (usually the actual subject)
        if len(keywords) > 3:
            logger.info(f"Too many keywords ({len(keywords)}), using first 3: {keywords[:3]}")
            keywords = keywords[:3]
        
        # Build JQL with AND for specificity
        if len(keywords) >= 2:
            logger.info(f"Keywords detected: {keywords} - using AND logic")
            conditions = [f'text ~ "{kw}"' for kw in keywords]
            jql = ' AND '.join(conditions)
        else:
            # Single keyword - search in summary and text
            keyword = keywords[0]
            jql = f'summary ~ "{keyword}" OR text ~ "{keyword}"'
            logger.info(f"Single keyword: {keyword}")
        
        jql += ' ORDER BY updated DESC'
        
        # Balance quotes if uneven
        if jql.count('"') % 2 != 0:
            jql += '"'
            logger.warning(f"Balanced uneven quotes in JQL")
        
        logger.info(f"Built keyword-based JQL: {jql}")
        return jql
    
    def build_jql_with_llm(self, message: str) -> Optional[str]:
        """
        Use LLM to intelligently generate JQL query.
        
        Args:
            message: User's natural language query
            
        Returns:
            JQL query string or None if LLM fails
        """
        try:
            prompt = f"""Convert this question into a Jira JQL query.

User question: "{message}"

Rules:
- Use summary~ for title searches, text~ for full-text
- When user mentions MULTIPLE keywords (e.g., "philosophy books"), use AND to require ALL keywords
- Example: "philosophy books" -> text~"philosophy" AND text~"books"
- For single keywords, use OR: summary~"keyword" OR text~"keyword"
- Add "ORDER BY updated DESC" at the end
- Return ONLY the JQL query, nothing else
- If user specifies status, use: status = "To Do" / "In Progress" / "Done"

Examples:
Q: "Show me all bugs in project ACTHUB"
A: project = ACTHUB AND type = Bug ORDER BY updated DESC

Q: "Find philosophy books to read"
A: text~"philosophy" AND text~"books" ORDER BY updated DESC

Q: "Montreal items"
A: summary~"montreal" OR text~"montreal" ORDER BY updated DESC

Generate JQL:"""
            
            response = self.llm.invoke(prompt)
            jql = response.content.strip()
            
            # Clean up response - remove markdown code blocks and backticks
            jql = jql.replace('```jql', '').replace('```', '').strip()
            # Remove leading/trailing backticks that LLMs sometimes add
            jql = jql.strip('`').strip()
            # Also remove backticks from within the JQL (LLM sometimes wraps entire query)
            if jql.startswith('`') or jql.endswith('`'):
                jql = jql.strip('`').strip()
            
            # Remove common LLM preamble patterns
            preamble_patterns = [
                r'^[Hh]ere\s+is.*?:\s*',
                r'^[Tt]he\s+JQL\s+query.*?:\s*',
                r'^[Gg]enerated\s+JQL.*?:\s*',
                r'^[Bb]ased\s+on.*?:\s*',
            ]
            for pattern in preamble_patterns:
                jql = re.sub(pattern, '', jql, flags=re.DOTALL)
            
            # If there are multiple lines, try to find the actual JQL
            lines = [l.strip() for l in jql.strip().split('\n') if l.strip()]
            for line in lines:
                # Look for lines that look like JQL (contain JQL keywords)
                if any(kw in line.lower() for kw in ['summary~', 'text~', 'project', 'status', 'order by', 'and', 'or']):
                    jql = line
                    break
            
            jql = jql.strip()
            
            # Validate it looks like JQL (contains JQL keywords/operators anywhere)
            jql_indicators = ['summary~', 'text~', 'summary ~', 'text ~', 'project =', 'project=',
                             'status =', 'status=', 'type =', 'type=', 'priority', 'assignee',
                             'order by', 'ORDER BY', 'and', 'AND', 'or', 'OR', 'parent =', 
                             'issuetype', 'key =', 'key=', 'created', 'updated']
            
            # Check if it contains ANY JQL indicator
            if any(indicator in jql.lower() or indicator in jql for indicator in jql_indicators):
                # Fix common JQL issues
                jql = self._sanitize_jql(jql)
                
                # Final cleanup: strip any remaining backticks
                jql = jql.strip('`').strip()
                
                # Balance quotes if uneven
                if jql.count('"') % 2 != 0:
                    jql += '"'
                    logger.warning(f"Balanced uneven quotes in LLM-generated JQL")
                
                logger.info(f"LLM generated JQL: {jql}")
                return jql
            else:
                logger.warning(f"LLM response doesn't look like valid JQL: {jql}")
                return None
                
        except Exception as e:
            logger.error(f"LLM JQL generation failed: {e}")
            return None
    
    def _sanitize_jql(self, jql: str) -> str:
        """
        Fix common JQL syntax issues.
        
        - Quote multi-word status values
        - Fix operator spacing
        """
        # Fix unquoted multi-word status values
        status_fixes = [
            (r'status\s*=\s*In Progress', 'status = "In Progress"'),
            (r'status\s*=\s*To Do', 'status = "To Do"'),
            (r'status\s*=\s*In Review', 'status = "In Review"'),
            (r'status\s*=\s*Code Review', 'status = "Code Review"'),
            (r'status\s*=\s*On Hold', 'status = "On Hold"'),
            (r'status\s*=\s*In QA', 'status = "In QA"'),
            (r'status\s*=\s*Ready for Dev', 'status = "Ready for Dev"'),
            (r'status\s*=\s*Ready for QA', 'status = "Ready for QA"'),
        ]
        
        for pattern, replacement in status_fixes:
            jql = re.sub(pattern, replacement, jql, flags=re.IGNORECASE)
        
        return jql
    
    def build_child_issues_query(self, parent_key: str) -> str:
        """
        Build JQL query to fetch child issues of a parent.
        
        Args:
            parent_key: Parent issue key (e.g., ACTHUB-9)
            
        Returns:
            JQL query string
        """
        return f"parent = {parent_key} ORDER BY created DESC"
    
    def build_multiple_parents_query(self, parent_keys: List[str]) -> str:
        """
        Build JQL query to fetch child issues of multiple parents.
        
        Args:
            parent_keys: List of parent issue keys
            
        Returns:
            JQL query string
        """
        if len(parent_keys) == 1:
            return self.build_child_issues_query(parent_keys[0])
        
        # Use IN clause for multiple parents
        keys_str = ', '.join(parent_keys)
        return f"parent IN ({keys_str}) ORDER BY created DESC"
    
    def build_status_filter_query(self, base_jql: str, status: str) -> str:
        """
        Add status filter to existing JQL query.
        
        Args:
            base_jql: Existing JQL query
            status: Status to filter ('to_do', 'in_progress', 'done')
            
        Returns:
            Modified JQL with status filter
        """
        status_map = {
            'to_do': '"To Do"',
            'in_progress': '"In Progress"',
            'done': '"Done"'
        }
        
        status_value = status_map.get(status, status)
        
        # Remove ORDER BY temporarily
        order_by = ''
        if 'ORDER BY' in base_jql.upper():
            parts = base_jql.upper().split('ORDER BY')
            base_jql = base_jql[:len(parts[0])]
            order_by = ' ORDER BY' + base_jql[len(parts[0]):]
        
        # Add status filter
        if base_jql.strip():
            jql = f"{base_jql} AND status = {status_value}{order_by}"
        else:
            jql = f"status = {status_value}{order_by}"
        
        return jql
    
    def build_intelligent_query(self, message: str, previous_error: str = None) -> str:
        """
        Build JQL using best available method (LLM first, fallback to keywords).
        
        Args:
            message: User's natural language query
            previous_error: Optional error from previous JQL attempt (for retry)
            
        Returns:
            JQL query string
        """
        # If we have a previous error, try LLM with error context
        if previous_error:
            jql = self.build_jql_with_error_feedback(message, previous_error)
            if jql:
                return jql
        
        # Try LLM first
        jql = self.build_jql_with_llm(message)
        
        # Fallback to keyword-based
        if not jql:
            logger.info("LLM query failed, falling back to keyword extraction")
            jql = self.build_jql_from_keywords(message)
        
        return jql
    
    def build_jql_with_error_feedback(self, message: str, error: str) -> Optional[str]:
        """
        Retry JQL generation with error feedback from Jira API.
        
        This allows the LLM to learn from its mistakes and fix the query.
        
        Args:
            message: Original user query
            error: Error message from Jira API
            
        Returns:
            Fixed JQL query or None
        """
        try:
            prompt = f"""The previous JQL query failed with this error from Jira:

ERROR: {error}

Original user question: "{message}"

Please generate a CORRECTED JQL query that fixes this error.

Common fixes:
- Multi-word status values must be quoted: status = "In Progress" (not: status = In Progress)
- Text searches use ~: text ~ "keyword" or summary ~ "keyword"
- Use proper AND/OR grouping with parentheses
- Valid statuses: "To Do", "In Progress", "Done", "Backlog"

Return ONLY the corrected JQL query, nothing else:"""
            
            response = self.llm.invoke(prompt)
            jql = response.content.strip()
            
            # Clean up and validate
            jql = jql.replace('```jql', '').replace('```', '').strip()
            jql = self._sanitize_jql(jql)
            
            # Remove any preamble
            lines = [l.strip() for l in jql.split('\n') if l.strip()]
            for line in lines:
                if any(kw in line.lower() for kw in ['summary~', 'text~', 'project', 'status', 'order by']):
                    jql = line
                    break
            
            logger.info(f"🔄 LLM corrected JQL after error: {jql}")
            return jql
            
        except Exception as e:
            logger.error(f"LLM JQL correction failed: {e}")
            return None
