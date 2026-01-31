# Integration Folder Reorganization

## New Structure

```
app/services/integrations/
├── atlassian/                          # Atlassian products
│   ├── __init__.py
│   ├── jira_service.py                 # Jira API integration
│   ├── confluence_service.py           # Confluence API integration
│   └── atlassian_mcp_client.py         # Model Context Protocol client
│
├── web/                                # Web search
│   ├── __init__.py
│   └── web_search_service.py           # DuckDuckGo + BeautifulSoup scraping
│
├── __init__.py
│
└── (legacy files - can be removed after migration)
    ├── jira_service.py
    ├── confluence_service.py
    ├── atlassian_mcp_client.py
    └── web_search_service.py
```

## Benefits

1. **Clear organization by vendor**
   - All Atlassian services in one place
   - Web services separate
   - Easy to add more vendors (GitHub, Slack, etc.)

2. **Scalability**
   - Add `app/services/integrations/github/` for GitHub integration
   - Add `app/services/integrations/slack/` for Slack integration
   - Each vendor isolated

3. **Maintainability**
   - Related services together
   - Clear imports: `from app.services.integrations.atlassian import jira_service`
   - Easy to find what you need

## Migration Steps

### Phase 1: Copy Files (✅ DONE)
- Copied files to new locations
- Kept originals for backwards compatibility

### Phase 2: Update Import Statements

**Files that need updating:**

1. `app/services/orchestration/mcp_operations.py`
   ```python
   # OLD:
   from app.services.integrations.atlassian_mcp_client import AtlassianMCPClient
   
   # NEW:
   from app.services.integrations.atlassian.atlassian_mcp_client import AtlassianMCPClient
   ```

2. `app/services/orchestration/search_orchestrator.py`
   ```python
   # OLD:
   from app.services.integrations.jira_service import jira_service
   from app.services.integrations.confluence_service import confluence_service
   from app.services.integrations.web_search_service import web_search_service
   
   # NEW:
   from app.services.integrations.atlassian.jira_service import jira_service
   from app.services.integrations.atlassian.confluence_service import confluence_service
   from app.services.integrations.web.web_search_service import web_search_service
   ```

3. `app/services/orchestration/jira_write_service.py`
   ```python
   # OLD:
   from app.services.integrations.jira_service import jira_service
   
   # NEW:
   from app.services.integrations.atlassian.jira_service import jira_service
   ```

4. `app/services/orchestration/clarification_service.py`
   ```python
   # OLD:
   from app.services.integrations.jira_service import jira_service
   
   # NEW:
   from app.services.integrations.atlassian.jira_service import jira_service
   ```

5. `app/services/knowledge/kg_query_service.py`
   ```python
   # OLD:
   from app.services.integrations.jira_service import jira_service
   
   # NEW:
   from app.services.integrations.atlassian.jira_service import jira_service
   ```

6. `app/services/core/ai_agent_service.py`
   ```python
   # OLD:
   from app.services.integrations.jira_service import jira_service
   from app.services.integrations.confluence_service import confluence_service
   from app.services.integrations.web_search_service import web_search_service
   from app.services.integrations.atlassian_mcp_client import AtlassianMCPClient
   
   # NEW:
   from app.services.integrations.atlassian.jira_service import jira_service
   from app.services.integrations.atlassian.confluence_service import confluence_service
   from app.services.integrations.web.web_search_service import web_search_service
   from app.services.integrations.atlassian.atlassian_mcp_client import AtlassianMCPClient
   ```

### Phase 3: Remove Legacy Files
After all imports are updated and tested:
```bash
rm app/services/integrations/jira_service.py
rm app/services/integrations/confluence_service.py
rm app/services/integrations/atlassian_mcp_client.py
rm app/services/integrations/web_search_service.py
```

## Future Extensions

### GitHub Integration
```
app/services/integrations/github/
├── __init__.py
├── github_api_service.py
├── github_issues_service.py
└── github_pr_service.py
```

### Slack Integration
```
app/services/integrations/slack/
├── __init__.py
├── slack_api_service.py
└── slack_channel_service.py
```

### Azure DevOps Integration
```
app/services/integrations/azure/
├── __init__.py
├── azure_boards_service.py
└── azure_repos_service.py
```

## Import Pattern

```python
# Recommended pattern:
from app.services.integrations.atlassian import jira_service
from app.services.integrations.web import web_search_service

# OR more explicit:
from app.services.integrations.atlassian.jira_service import jira_service
from app.services.integrations.web.web_search_service import web_search_service
```

## Testing After Migration

1. Test Jira operations (search, get issue, create, update)
2. Test Confluence search
3. Test web search and scraping
4. Test MCP operations
5. Test all AI agent chat scenarios
6. Verify no import errors

## Rollback Plan

If issues arise:
1. Revert import changes
2. Keep using legacy files
3. New files remain as backup
