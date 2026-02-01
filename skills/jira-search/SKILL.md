---
name: jira-search
description: Search Jira issues using natural language queries, JQL, or keywords. Use when the user asks to find, search, list, or query Jira issues by topic, status, assignee, or any criteria. Handles complex queries requiring JQL generation or simple keyword matching.
---

# Jira Search

Search Jira issues intelligently using natural language, JQL queries, or keyword extraction.

## Overview

This skill enables searching Jira issues with multiple strategies:
1. **Direct issue keys** - When user mentions specific issue IDs (ACTHUB-123)
2. **LLM-generated JQL** - Complex queries needing structured search
3. **Keyword extraction** - Fallback for simple topic searches

## When to Use

Triggers on queries like:
- "Find issues about climbing"
- "Show me open bugs"  
- "What tasks are in progress?"
- "Search for issues by John"
- "List all epics in ACTHUB project"

## Workflow

1. **Analyze query intent** 
   - Check for direct issue keys (ACTHUB-9)
   - Determine query complexity
   
2. **Choose strategy**
   - **Simple**: Use keyword extraction for topic searches
   - **Complex**: Generate JQL for status/type/assignee filters
   - **Direct**: Fetch specific issues by key

3. **Execute search**
   - Run generated or extracted query
   - If no results, try fallback strategy
   
4. **Verify results**
   - Check if results match user intent
   - Filter irrelevant matches

## JQL Generation

See [references/jql_examples.md](references/jql_examples.md) for JQL patterns.

### Strategy Selection

**Use LLM-generated JQL when:**
- Query mentions specific fields (status, type, assignee, priority)
- User wants filtering or sorting
- Complex boolean logic needed

**Use keyword extraction when:**
- Simple topic search ("find climbing issues")
- No specific field criteria mentioned
- User asks about content/subject matter

## Examples

**Input**: "Show me climbing tasks or epics I created"
**Strategy**: LLM-generated JQL
**Output**: `creator = currentUser() AND text ~ "climbing" AND type IN (Task, Epic)`

**Input**: "Find issues about garbage collection"
**Strategy**: Keyword extraction
**Output**: `text ~ "garbage" AND text ~ "collection" ORDER BY updated DESC`

**Input**: "Get ACTHUB-322"
**Strategy**: Direct fetch
**Output**: Fetches specific issue

## Error Handling

If PRIMARY query fails:
1. Try FALLBACK query (broader criteria)
2. If both fail, use keyword extraction
3. Always sort by updated DESC for recency

## Integration

Results automatically:
- ✅ Added to Knowledge Graph
- ✅ Verified for relevance  
- ✅ Enriched with KG context
