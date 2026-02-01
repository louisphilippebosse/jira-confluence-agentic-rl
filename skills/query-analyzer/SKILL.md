---
name: query-analyzer
description: |
  Analyzes user queries to extract intent, entities, and context.
  Enhances the existing query understanding in ai_agent_service.
type: intelligence
wrapper: true
---

# Skill: query-analyzer

## Purpose
This skill wraps and enhances the existing `QueryAnalyzerService` by adding LLM-powered intent understanding.

## What It Does

### Input
- User's natural language query
- Conversation history (optional)

### Processing
1. Extract entities (issue keys, project names, people)
2. Determine intent (search, analyze, get details, etc.)
3. Identify required data sources (Jira, Confluence, KG)
4. Extract time-based context (latest, recent, last week)
5. Identify relationships (child issues, related pages)

### Output
```python
{
    "intent": "search_jira_issues",
    "entities": {
        "issue_keys": ["PROJ-123"],
        "projects": ["PROJ"],
        "people": ["John Doe"],
        "keywords": ["docker", "bug"]
    },
    "data_sources": ["jira", "knowledge_graph"],
    "time_context": {
        "type": "recent",
        "window": "7d"
    },
    "relationship_query": {
        "type": "child_issues",
        "parent_key": "PROJ-123"
    },
    "confidence": 0.95
}
```

## Integration Point

**Before**: `ai_agent_service.chat()` uses basic keyword matching
**After**: Uses this skill to get structured intent analysis

```python
# In ai_agent_service.chat()
if use_skill_enhancement:
    analysis = await skill_middleware.execute("query-analyzer", message, context_history)
    # Use analysis.intent to route intelligently
    # Use analysis.entities to improve searches
```

## Wraps Existing
- `QueryAnalyzerService.is_asking_for_children()`
- `QueryAnalyzerService.extract_single_issue_key()`
- Adds: Entity extraction, intent classification, confidence scoring
