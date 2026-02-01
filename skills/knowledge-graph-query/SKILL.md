---
name: knowledge-graph-query
description: Query the Knowledge Graph for cached Jira issues and Confluence pages using semantic search and community summaries. Use when enriching search results with historical context, finding related entities, or when fresh API data needs historical perspective.
---

# Knowledge Graph Query

Search the cached knowledge graph for historical Jira and Confluence data using semantic search and community detection.

## Overview

The Knowledge Graph stores previously fetched Jira issues and Confluence pages with relationships. This skill provides:
- **Semantic text search** across cached entities
- **Community summaries** for high-level insights
- **Relationship traversal** (parent/child issues, epics)
- **Central entity discovery** (most connected items)

## When to Use

**Primary use cases:**
1. **Enrichment** - Add context to fresh search results
2. **Historical queries** - "What was the status of X last month?"
3. **Relationship discovery** - "What's related to this issue?"
4. **Pattern finding** - "Show me all issues in this community"

**NOT for:**
- Fresh/current data (use jira-search or confluence-search)
- Creating new data
- Real-time status checks

## Workflow

1. **Determine entity type filter**
   - If querying with Jira context → filter to `jira_issue`
   - If querying with Confluence context → filter to `confluence_page`
   - If mixed/unknown → no filter (search all)

2. **Execute semantic search**
   - Extract keywords from query
   - Search graph by text similarity
   - Optionally filter by entity type

3. **Get community context** (if available)
   - Find relevant communities for query
   - Return top 3 community summaries

4. **Format results**
   - Return related entity keys/titles
   - Include community insights
   - Note central/important entities

## Integration with Other Skills

**Used alongside:**
- `jira-search` - KG provides historical context for fresh results
- `confluence-search` - KG enriches with related pages
- `multi-source-synthesizer` - KG is one of multiple sources

**Always runs after** primary search skills to enrich results.

## Entity Types

- `jira_issue` - Jira issues with summaries, statuses, relationships
- `confluence_page` - Confluence pages with titles, content
- `project` - Jira projects
- `user` - Assignees, reporters
- `label`, `component` - Issue metadata

## Examples

**Query**: "Find climbing issues"  
**With context**: Jira  
**Action**: Search KG filtered to `jira_issue`, return keys like ACTHUB-322

**Query**: "Garbage collection documentation"  
**With context**: Confluence  
**Action**: Search KG filtered to `confluence_page`, return page titles

## Limitations

- Only contains previously fetched data
- Not real-time (use fresh search for current data)
Communities require `python -m app.maintenance.build_communities` to have been run
