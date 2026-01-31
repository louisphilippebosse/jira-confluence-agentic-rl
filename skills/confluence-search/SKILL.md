---
name: confluence-search
description: |
  Search Confluence wiki pages by keywords, titles, or content.
  Supports space filtering (including personal spaces) and keyword extraction.
  Returns page summaries with links.
---

# Skill: confluence-search

## Overview
This skill searches Confluence wiki pages to find documentation, notes, meeting records, and other knowledge artifacts. It can search across all spaces or filter to specific spaces (like a user's personal space).

## When to Use
Use this skill when the user asks about:
- Finding pages/documents in Confluence
- Looking up documentation or notes
- Searching for specific topics in wikis
- Questions like "do I have any pages about X?"
- References to "my space", "personal space", or specific Confluence spaces

## Search Strategies

### 1. **Keyword Extraction**
Best for natural language queries:
- Extract meaningful keywords from the query
- Remove stop words (the, a, is, etc.)
- Search using CQL (Confluence Query Language)

### 2. **Space Filtering**
When user mentions:
- "my space" / "personal space" → Use configured personal space key
- Specific space key → Filter to that space
- No mention → Search all spaces

### 3. **Content Fetching**
After finding pages:
- Fetch full page content (up to 2000 chars)
- Extract snippets relevant to query
- Provide direct links for user to access

## Workflow

1. **Parse Query**
   ```
   Input: "Do I have any pages about Docker containers?"
   Keywords: ["Docker", "containers"]
   Space: Personal space (if configured)
   ```

2. **Execute Search**
   ```
   CQL: text ~ "Docker" AND text ~ "containers" AND space = "~accountid"
   ```

3. **Fetch Content**
   ```
   For each result:
   - Get full page content
   - Extract title, excerpt, link
   ```

4. **Return Results**
   ```json
   {
     "keywords": ["Docker", "containers"],
     "space": "~7120200cdcd290d375488287f9f21afc27e59d",
     "pages": [
       {
         "title": "Docker Setup Guide",
         "excerpt": "...",
         "link": "https://..."
       }
     ]
   }
   ```

## Examples

### Example 1: Personal Space Search
```
Query: "What notes do I have about the pipeline?"
Result: Searches personal space for pages containing "notes", "pipeline"
```

### Example 2: All Spaces Search
```
Query: "Find documentation about API endpoints"
Result: Searches all spaces for "documentation", "API", "endpoints"
```

### Example 3: Space-Specific Search
```
Query: "Search the DEV space for deployment guides"
Result: Searches space "DEV" for "deployment", "guides"
```

## Configuration

Required environment variables:
- `CONFLUENCE_URL`: Confluence instance URL
- `CONFLUENCE_USERNAME`: Username for API access
- `CONFLUENCE_TOKEN`: API token or password
- `CONFLUENCE_PERSONAL_SPACE`: (Optional) Personal space key (e.g., `~accountid`)

## CQL Reference

Common CQL patterns:
- `text ~ "keyword"`: Contains keyword in any field
- `title ~ "keyword"`: Keyword in title
- `space = "KEY"`: Filter to specific space
- `type = "page"`: Only pages (not blog posts)
- `lastModified >= "2024-01-01"`: Date filters

Operators: `AND`, `OR`, `NOT`

## Limitations
- CQL search may not match partial words
- Personal space key format: `~accountid` (tilde + user account ID)
- Content fetched is truncated to 2000 characters
- Results limited to 10 pages by default

## Integration Points
- Often used with **knowledge-graph-query** to enrich results
- Can feed into **multi-source-synthesizer** with Jira results
- May trigger **result-analyzer** to extract specific data
