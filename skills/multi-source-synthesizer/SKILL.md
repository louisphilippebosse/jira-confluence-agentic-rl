---
name: multi-source-synthesizer
description: |
  Combines and synthesizes results from multiple data sources (Jira, Confluence, Knowledge Graph)
  into a coherent, comprehensive answer. Deduplicates, cross-references, and enriches data.
---

# Skill: multi-source-synthesizer

## Overview
This skill is invoked when multiple other skills have gathered data and need to be combined into a single, coherent response. It acts as the "final assembly" step, ensuring the user gets a complete picture from all available sources.

## When to Use
Use this skill when:
- Multiple search skills have been executed (Jira + Confluence + KG)
- Results need to be deduplicated and cross-referenced
- Context from one source can enrich another source's data
- User needs a unified answer combining multiple data types

**Trigger Indicators:**
- "Tell me everything about..."
- "What's the status of... (checking both Jira issues AND docs)"
- "Find all information related to..."
- Multi-skill execution has occurred

## Synthesis Strategies

### 1. **Cross-Referencing**
Link related items across sources:
- Jira issue KEY-123 mentioned in Confluence page → Add page link to issue summary
- Person mentioned in Jira and KG → Enrich with KG relationships
- Project in Confluence docs + Jira issues → Show both contexts

### 2. **Deduplication**
Remove redundant information:
- Same Jira issue from multiple queries → Show once with combined context
- Duplicate Confluence pages → Keep most recent or relevant
- Repeated KG entities → Consolidate relationships

### 3. **Enrichment**
Add context from supporting sources:
- Jira issue → Add related Confluence docs
- Confluence page → Add related Jira issues
- KG entities → Add community/cluster information

### 4. **Prioritization**
Order results by relevance:
- Direct matches first
- Related items second
- Background/context third

## Workflow

1. **Collect Results**
   ```
   Input:
   - jira-search: [ISSUE-1, ISSUE-2]
   - confluence-search: [Page A, Page B]
   - knowledge-graph-query: [Entity X relates to Entity Y]
   ```

2. **Identify Cross-References**
   ```
   - ISSUE-1 mentions "Page A" → Link them
   - Page B links to ISSUE-2 → Cross-reference
   - Entity X = ISSUE-1 → Enrich with KG data
   ```

3. **Deduplicate**
   ```
   - ISSUE-1 appeared in 2 searches → Keep one
   - Page A content + Page A link → Merge
   ```

4. **Synthesize Answer**
   ```
   Structure:
   1. Direct answer to query
   2. Primary sources (Jira issues)
   3. Supporting documentation (Confluence)
   4. Additional context (KG relationships)
   5. Related items
   ```

5. **Return Structured Response**
   ```json
   {
     "answer": "Based on Jira, Confluence, and historical data...",
     "sources": {
       "jira": [...],
       "confluence": [...],
       "knowledge_graph": [...]
     },
     "cross_references": [...],
     "summary": "..."
   }
   ```

## Examples

### Example 1: Issue + Documentation
```
Input:
- Jira: [DEPLOY-45 "Pipeline failure"]
- Confluence: ["Pipeline Setup Guide"]
- KG: [DEPLOY-45 relates to "CI/CD" cluster]

Output:
"Issue DEPLOY-45 reports a pipeline failure. According to the Pipeline Setup Guide,
this likely relates to [step X]. The Knowledge Graph shows this issue is part of
a cluster of CI/CD-related items, including DEPLOY-40, DEPLOY-41..."
```

### Example 2: Person-Centric Query
```
Input:
- Jira: [3 issues assigned to "John Doe"]
- KG: [John Doe worked on Projects A, B, C]
- Confluence: [John's meeting notes page]

Output:
"John Doe currently has 3 open issues: KEY-1, KEY-2, KEY-3. He has historically
worked on Projects A, B, and C. His personal space contains meeting notes about..."
```

### Example 3: Project Overview
```
Input:
- Jira: [15 issues in project ALPHA]
- Confluence: [5 pages tagged "Project Alpha"]
- KG: [Project Alpha community includes 8 related concepts]

Output:
"Project ALPHA has 15 open issues across 3 epics. Documentation includes setup guides,
architecture docs, and meeting notes. Related concepts in the knowledge base include..."
```

## Synthesis Principles

### Clarity
- Start with direct answer
- Avoid repetition
- Use clear section headers

### Completeness
- Include all relevant sources
- Don't omit data sources that contributed
- Show relationships between items

### Attribution
- Clearly state which source provided which information
- Link back to original data (Jira keys, Confluence URLs)
- Indicate confidence levels ("likely", "confirmed", "mentioned")

### Actionability
- Highlight actionable items
- Provide direct links
- Suggest next steps if appropriate

## Data Structures

### Input Format
```python
{
  "query": "original user query",
  "skill_results": [
    {
      "skill": "jira-search",
      "success": True,
      "data": {...}
    },
    {
      "skill": "confluence-search",
      "success": True,
      "data": {...}
    },
    {
      "skill": "knowledge-graph-query",
      "success": True,
      "data": {...}
    }
  ]
}
```

### Output Format
```python
{
  "answer": "Synthesized natural language answer",
  "sources": {
    "jira": ["KEY-1", "KEY-2"],
    "confluence": ["Page A", "Page B"],
    "kg": ["Entity X", "Entity Y"]
  },
  "cross_references": [
    {"type": "jira-confluence", "from": "KEY-1", "to": "Page A"},
    {"type": "jira-kg", "from": "KEY-1", "to": "Entity X"}
  ],
  "summary": "Brief summary if answer is long",
  "metadata": {
    "sources_used": 3,
    "total_items": 10,
    "confidence": "high"
  }
}
```

## Integration Points
- **Receives from:** All search skills (jira-search, confluence-search, knowledge-graph-query)
- **Uses:** Result verifier for validation
- **Outputs to:** User as final response

## Performance Considerations
- Limit to top N results per source (avoid overwhelming user)
- Use LLM selectively (only for complex synthesis, not simple merging)
- Cache cross-reference lookups
- Timeout for large result sets
