---
name: result-ranker
description: |
  Ranks and filters search results for relevance.
  Enhances the existing ResultVerifier with confidence scoring.
type: intelligence
wrapper: true
---

# Skill: result-ranker

## Purpose
Wraps and enhances the existing `ResultVerifier` to provide better result filtering with confidence scores.

## What It Does

### Input
- User query
- Raw search results (Jira issues, Confluence pages)
- Query analysis (from query-analyzer skill)

### Processing
1. Score each result for relevance (0-1)
2. Filter out low-confidence matches (< 0.3)
3. Rank by relevance, recency, and importance
4. Group related results (same epic, same project)
5. Limit to top N most relevant

### Output
```python
{
    "ranked_results": [
        {
            "item": {...},  # Original Jira/Confluence object
            "relevance_score": 0.95,
            "reasons": ["Exact keyword match", "Recent update", "Direct assignment"],
            "rank": 1
        },
        ...
    ],
    "filtered_out": 5,  # Number of irrelevant results removed
    "grouping": {
        "by_epic": {"PROJ-100": [...]},
        "by_status": {"In Progress": [...]}
    }
}
```

## Integration Point

**Before**: `ResultVerifier.verify_json_string()` does basic filtering
**After**: Adds relevance scoring and ranking

```python
# In ai_agent_service.chat() after search
jira_results = await self._intelligent_jira_search(message)

if use_skill_enhancement:
    ranked = await skill_middleware.execute("result-ranker", message, jira_results, analysis)
    filtered_result = ranked["ranked_results"][:10]  # Top 10
else:
    # Legacy verification
    filtered_result = self._verify_and_filter_results(message, jira_results)
```

## Wraps Existing
- `ResultVerifier.verify_json_string()`
- `ResultVerifier.verify_and_rank()`
- Adds: Confidence scoring, grouping, advanced ranking
