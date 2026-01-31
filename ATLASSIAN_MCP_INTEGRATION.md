# Atlassian MCP Integration

This project integrates with Atlassian's official Rovo MCP Server to provide seamless Jira and Confluence access through the Model Context Protocol.

## What is MCP?

Model Context Protocol (MCP) is a standardized protocol that enables AI assistants to securely connect to external tools and data sources. Think of it as a universal API for AI agents.

## Architecture

```
AI Agent Service (Your Code)
       ↓
AtlassianMCPClient (app/services/atlassian_mcp_client.py)
       ↓
mcp-remote Proxy (Local Bridge)
       ↓
Atlassian Rovo MCP Server (https://mcp.atlassian.com/v1/mcp)
       ↓
Your Jira & Confluence Cloud
```

## Setup Instructions

### 1. Install mcp-remote Proxy

The proxy bridges your local code to Atlassian's cloud MCP server:

```bash
npm install -g @modelcontextprotocol/mcp-remote
```

### 2. Configure Atlassian OAuth

You need OAuth credentials from Atlassian:

1. Go to https://developer.atlassian.com/console/myapps/
2. Create a new OAuth 2.0 integration
3. Add these scopes:
   - `read:jira-work`
   - `read:jira-user`
   - `read:confluence-content.all`
   - `read:confluence-space.summary`
4. Set redirect URI: `http://localhost:3000/oauth/callback`
5. Note your Client ID and Client Secret

### 3. Start the MCP Proxy

```bash
export ATLASSIAN_CLIENT_ID="your_client_id"
export ATLASSIAN_CLIENT_SECRET="your_client_secret"
export ATLASSIAN_SITE_URL="https://your-site.atlassian.net"

mcp-remote --server https://mcp.atlassian.com/v1/mcp --port 3000
```

On Windows PowerShell:
```powershell
$env:ATLASSIAN_CLIENT_ID="your_client_id"
$env:ATLASSIAN_CLIENT_SECRET="your_client_secret"
$env:ATLASSIAN_SITE_URL="https://your-site.atlassian.net"

mcp-remote --server https://mcp.atlassian.com/v1/mcp --port 3000
```

### 4. Configure Your Application

Update your `.env` file:

```env
# Enable MCP (set to false to use direct API)
ENABLE_MCP=true

# MCP proxy URL (where mcp-remote is running)
MCP_PROXY_URL=http://localhost:3000
```

### 5. Start Your Application

```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows Git Bash
# or
.venv\Scripts\activate.bat  # Windows CMD

# Install aiohttp if not already installed
pip install aiohttp>=3.9.0

# Start the backend
uvicorn app.main:app --reload
```

## How It Works

### Automatic Fallback

The integration intelligently falls back to direct API calls if MCP is unavailable:

1. **MCP First**: Tries to use Atlassian's MCP server for all Jira/Confluence operations
2. **Direct API Fallback**: If MCP fails or is disabled, uses your existing Jira/Confluence services
3. **Seamless**: No code changes needed in your queries

### Available MCP Tools

The Atlassian MCP server provides these tools:

- `atlassian_jira_jql` - Search Jira issues using JQL
- `atlassian_jira_issue` - Get details for a specific issue
- `atlassian_confluence_search` - Search Confluence pages
- `atlassian_confluence_page` - Get a specific page
- `atlassian_compass` - Access Compass component data

### Example Usage

Your existing code works unchanged:

```python
# Your agent automatically uses MCP when available
response = await ai_agent_service.chat(
    message="show me open bugs in PROJ",
    session_id="123",
    conversation_history=[]
)
```

Behind the scenes:
1. Builds JQL query: `project=PROJ AND type=Bug AND status in (Open, "In Progress")`
2. Tries MCP: `atlassian_jira_jql` tool
3. Falls back to `jira_service.search_issues()` if MCP unavailable
4. Returns results formatted by your AI

## Benefits of MCP

### 1. **Reduced Maintenance**
- Atlassian maintains the integration
- Automatic updates to API changes
- No need to handle authentication complexity

### 2. **Better Performance**
- Optimized queries by Atlassian
- Built-in caching
- Reduced API rate limiting

### 3. **Enhanced Security**
- OAuth 2.1 with PKCE
- Token refresh handled automatically
- Scoped permissions

### 4. **Future-Proof**
- New Atlassian products automatically supported
- Community-driven protocol improvements
- Works with multiple AI providers

## Disabling MCP

To use direct API calls only (your existing integration):

```env
ENABLE_MCP=false
```

Your app will work exactly as before, using `jira_service` and `confluence_service` directly.

## Troubleshooting

### MCP Proxy Not Starting

```bash
# Check if port 3000 is already in use
netstat -an | grep 3000

# Try a different port
mcp-remote --server https://mcp.atlassian.com/v1/mcp --port 3001

# Update .env
MCP_PROXY_URL=http://localhost:3001
```

### Authentication Errors

```bash
# Check your OAuth credentials
curl http://localhost:3000/v1/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### MCP Calls Timing Out

Check logs for:
- `⚠️ MCP initialization failed` - Proxy not running
- `⚠️ MCP search failed` - Network or auth issue
- `✅ MCP returned X issues` - Working correctly

### Falling Back to Direct API

If you see `falling back to direct API` in logs:
1. Check mcp-remote is running: `curl http://localhost:3000`
2. Verify `ENABLE_MCP=true` in `.env`
3. Check network connectivity to Atlassian

## Development vs Production

### Development
- Run mcp-remote locally
- Use `MCP_PROXY_URL=http://localhost:3000`
- Enable detailed logging

### Production
- Deploy mcp-remote as a service
- Use internal network URL for proxy
- Configure proper OAuth redirect URIs
- Set `ENABLE_MCP=true` and monitor fallback rates

## Monitoring

Add these log patterns to your monitoring:

```python
# Success
logger.info("✅ MCP returned 5 issues")

# Fallback
logger.warning("⚠️ MCP search failed: timeout, falling back to direct API")

# Complete failure
logger.error("Error in Jira search: Network unreachable")
```

## Next Steps

1. Test with MCP disabled to ensure direct API still works
2. Start mcp-remote proxy
3. Enable MCP and test queries
4. Monitor fallback rates
5. Optimize based on usage patterns

## Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [Atlassian MCP Server](https://developer.atlassian.com/platform/mcp/)
- [mcp-remote Tool](https://github.com/modelcontextprotocol/mcp-remote)
