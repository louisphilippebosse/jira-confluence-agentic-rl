---
name: kg-enricher
description: |
  Enriches search results with Knowledge Graph context.
  Wraps existing KG service methods to add relevant insights.
type: intelligence
wrapper: true
---

# Skill: kg-enricher

## Purpose
Wraps and enhances the existing `KnowledgeGraphService` to provide smart context enrichment.

## What It Does

### Input
- User query
- Search results (already filtered/ranked)
- Query analysis (from query-analyzer skill)

### Processing
1. Search KG for related entities
2. Find community summaries relevant to query
3. Identify central/important entities
4. Extract relationships between results
5. Add historical context (previous updates, linked items)

### Output
```python
{
    "enriched_results": [
        {
            "item": {...},  # Original result
            "kg_context": {
                "related_issues": ["PROJ-101", "PROJ-102"],
                "related_pages": ["Docker Setup Guide"],
                "community": "Infrastructure & DevOps",
                "centrality": 0.75,  # Importance score
                "last_updated": "2026-01-15"
            }
        },
        ...
    ],
    "global_context": {
        "relevant_communities": ["Infrastructure & DevOps", "Backend Services"],
        "central_entities": ["Docker", "CI/CD Pipeline"],
        "total_related": 15
    }
}
```

## Integration Point

**Before**: `_get_kg_context_for_query()` provides basic context string
**After**: Structured enrichment data for each result

```python
# In ai_agent_service.chat() after filtering
filtered_results = self._verify_and_filter_results(message, jira_results)

if use_skill_enhancement:
    enriched = await skill_middleware.execute("kg-enricher", message, filtered_results, analysis)
    final_results = enriched["enriched_results"]
    kg_insights = enriched["global_context"]
else:
    # Legacy KG context (string)
    kg_context = self._get_kg_context_for_query(message)
```

## Wraps Existing
- `KnowledgeGraphService.search_by_text()`
- `KnowledgeGraphService.get_community_for_query()`
- `KnowledgeGraphService.get_central_entities()`
- Adds: Per-result enrichment, relationship discovery, structured output
