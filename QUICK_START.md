# Quick Start: Using Your New MCP Server and Knowledge Graph

## 🎉 What You Just Got

Congratulations! Your project now has:

1. ✅ **MCP Server** - Exposes Jira/Confluence as AI-accessible tools
2. ✅ **Knowledge Graph** - 107 nodes with 103 relationships
3. ✅ **CLI Tool** - Easy command-line access to everything
4. ✅ **Python Execution** - Run queries directly in VS Code

## 📊 Current Knowledge Graph

- **103 Jira Issues** (from the last year)
- **2 Confluence Pages**
- **2 Users** (Louis-Philippe Bossé, Unassigned)
- **103 Relationships** between entities

## 🚀 Quick Examples

### 1. Python Code Execution (What You Just Used!)

The Python execution tool you experienced is **already available** in VS Code through the Pylance MCP server. Just ask Copilot to run Python code for you, like:

```
"Can you run Python code to show me all my blocked Jira issues?"
```

Copilot will automatically:
- Generate the Python code
- Execute it using the `mcp_pylance_mcp_s_pylanceRunCodeSnippet` tool
- Show you formatted results

**Example queries you can try:**
- "Show me all issues assigned to me"
- "Get the status breakdown for project ACTHUB"
- "Find all issues updated in the last 7 days"
- "Show me the knowledge graph statistics"

### 2. CLI Commands

```bash
# View statistics
python kg_cli.py stats

# Search for specific entities
python kg_cli.py search --type jira_issue --limit 10

# Find related entities
python kg_cli.py related ACTHUB-9

# Refresh the knowledge graph (weekly recommended)
python kg_cli.py populate
```

### 3. Using the MCP Server with AI Assistants

Your MCP server (`mcp_server.py`) can be connected to:
- Claude Desktop
- Other MCP-compatible AI assistants
- Custom integrations

**Tools available:**
- `search_jira_issues` - Search with JQL
- `get_jira_issue` - Get specific issue details
- `get_child_issues` - Get all subtasks
- `search_confluence` - Search documentation
- `get_knowledge_graph_stats` - View KG stats
- `populate_knowledge_graph` - Bulk populate KG
- And more!

## 💡 Real-World Usage

### Scenario 1: Daily Standup Prep
```
Ask Copilot: "Show me all my issues that are in progress and any blockers"
```

Copilot will:
1. Generate Python code
2. Query Jira through your services
3. Format a nice summary

### Scenario 2: Sprint Planning
```
Ask Copilot: "Analyze the ACTHUB project - show status breakdown and who's working on what"
```

### Scenario 3: Documentation Search
```
Ask Copilot: "Find Confluence pages about deployment process"
```

### Scenario 4: Explore Relationships
```
Ask Copilot: "Show me all issues related to ACTHUB-9 and their current status"
```

The knowledge graph will reveal:
- Child issues
- Assigned users
- Related components
- Linked pages

## 🔄 How the Knowledge Graph Updates

The knowledge graph automatically updates when you:

1. **Use the chat interface** - Every Jira/Confluence query adds to the graph
2. **Run the CLI tool** - `python kg_cli.py populate`
3. **Use the MCP server** - All tool calls update the graph
4. **Run Python code** - When you query services directly

**Recommendation:** Run `python kg_cli.py populate` weekly to keep it fresh.

## 📚 Full Documentation

- **[MCP_AND_TOOLS_GUIDE.md](MCP_AND_TOOLS_GUIDE.md)** - Complete guide with examples
- **[KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md)** - Knowledge graph details
- **[README.md](README.md)** - Project overview

## 🎯 Next Steps

1. **Try asking Copilot natural language questions** about your Jira issues
2. **Explore the knowledge graph** with `python kg_cli.py search`
3. **Configure the MCP server** for Claude Desktop (optional)
4. **Set up weekly KG refresh** to keep data current

## 🛠️ Troubleshooting

**Problem:** Python code execution not working
- Make sure Pylance extension is installed
- Reload VS Code window

**Problem:** Jira/Confluence connection issues
- Check your `.env` file has valid credentials
- Run `python kg_cli.py test` to verify

**Problem:** Knowledge graph empty
- Run `python kg_cli.py populate`
- Check `ENABLE_KNOWLEDGE_GRAPH=true` in `.env`

## 💬 Example Conversation

**You:** "Tell me about the child issues of read 12 books in 2025"

**Copilot:** [Runs Python code to query Jira]
- Total: 12 books
- Done: 7
- In Progress: 2 (Network Models in Finance, Venture Deals)
- To Do: 3

**You:** "Show me all my blocked issues"

**Copilot:** [Queries Jira with JQL: `assignee = currentUser() AND status = Blocked`]
- Lists your blocked issues

**You:** "What's the most central entity in the knowledge graph?"

**Copilot:** [Runs PageRank analysis]
- Most central: user:Louis-Philippe Bossé (you're well-connected!)

---

Enjoy your enhanced Jira-Confluence AI system! 🚀
