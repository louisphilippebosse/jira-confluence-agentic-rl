#!/usr/bin/env python3
"""
MCP Server for Jira-Confluence Agentic RL Project

This Model Context Protocol (MCP) server exposes Jira and Confluence services
as tools that can be used by AI assistants like Claude Desktop, Copilot, etc.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

# Setup application imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.jira_service import jira_service
from app.services.confluence_service import confluence_service
from app.services.knowledge_graph_service import knowledge_graph_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-jira-confluence")

# Create MCP server
app = Server("jira-confluence-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for Jira and Confluence"""
    return [
        Tool(
            name="search_jira_issues",
            description="Search Jira issues using JQL (Jira Query Language). Examples: 'project = ACTHUB', 'status = \"In Progress\"', 'assignee = currentUser()', 'summary ~ \"books\"'",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50
                    }
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="get_jira_issue",
            description="Get detailed information about a specific Jira issue by its key (e.g., ACTHUB-9)",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., ACTHUB-9, PROJ-123)"
                    }
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="get_child_issues",
            description="Get all child issues (subtasks) of a parent Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_key": {
                        "type": "string",
                        "description": "Parent Jira issue key"
                    }
                },
                "required": ["parent_key"]
            }
        ),
        Tool(
            name="search_confluence",
            description="Search Confluence documentation and pages",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for Confluence"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_confluence_page",
            description="Get content from a specific Confluence page by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Confluence page ID"
                    }
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="get_knowledge_graph_stats",
            description="Get statistics about the knowledge graph including node counts, entity types, and relationships",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="populate_knowledge_graph",
            description="Populate the knowledge graph with all Jira issues and Confluence pages. This may take a while.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="search_knowledge_graph",
            description="Search for entities in the knowledge graph by type or properties",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Filter by entity type (jira_issue, confluence_page, user, component)",
                        "enum": ["jira_issue", "confluence_page", "user", "component", "confluence_space"]
                    },
                    "property_filter": {
                        "type": "object",
                        "description": "Filter by entity properties (e.g., {\"status\": \"In Progress\"})"
                    }
                },
            }
        ),
        Tool(
            name="get_related_entities",
            description="Get entities related to a specific entity in the knowledge graph",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID (e.g., ACTHUB-9, confluence:12345)"
                    },
                    "relationship_type": {
                        "type": "string",
                        "description": "Filter by relationship type (assigned_to, child_of, belongs_to_epic, etc.)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to search (default: 2)",
                        "default": 2
                    }
                },
                "required": ["entity_id"]
            }
        ),
        Tool(
            name="create_jira_issue",
            description="⚠️ WRITE OPERATION - Create a new Jira issue. Requires user approval before execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Project key (e.g., ACTHUB, LIFEOPS, SE)"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Issue summary/title"
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Issue type (Task, Story, Bug, Epic, Subtask)",
                        "default": "Task"
                    },
                    "description": {
                        "type": "string",
                        "description": "Issue description"
                    },
                    "parent_key": {
                        "type": "string",
                        "description": "Parent issue key for subtasks"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Assignee username"
                    },
                    "approval_required": {
                        "type": "boolean",
                        "description": "Internal flag - always true for safety",
                        "default": true
                    }
                },
                "required": ["project_key", "summary"]
            }
        ),
        Tool(
            name="update_jira_issue",
            description="⚠️ WRITE OPERATION - Update an existing Jira issue. Requires user approval before execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key to update (e.g., ACTHUB-9)"
                    },
                    "summary": {
                        "type": "string",
                        "description": "New summary/title"
                    },
                    "description": {
                        "type": "string",
                        "description": "New description"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "New assignee username"
                    },
                    "approval_required": {
                        "type": "boolean",
                        "description": "Internal flag - always true for safety",
                        "default": true
                    }
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="transition_jira_issue",
            description="⚠️ WRITE OPERATION - Change issue status (e.g., move to In Progress, Done). Requires user approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key (e.g., ACTHUB-9)"
                    },
                    "transition_name": {
                        "type": "string",
                        "description": "Target status (To Do, In Progress, Done, etc.)"
                    },
                    "approval_required": {
                        "type": "boolean",
                        "description": "Internal flag - always true for safety",
                        "default": true
                    }
                },
                "required": ["issue_key", "transition_name"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "search_jira_issues":
            jql = arguments["jql"]
            max_results = arguments.get("max_results", 50)
            
            logger.info(f"Searching Jira with JQL: {jql}")
            results = jira_service.search_issues(jql, max_results=max_results)
            
            # Add to knowledge graph
            for issue in results:
                knowledge_graph_service.add_jira_issue(issue)
            
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "get_jira_issue":
            issue_key = arguments["issue_key"]
            
            logger.info(f"Getting Jira issue: {issue_key}")
            result = jira_service.get_issue(issue_key)
            
            if result:
                # Add to knowledge graph
                knowledge_graph_service.add_jira_issue(result)
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Issue {issue_key} not found"
                )]
        
        elif name == "get_child_issues":
            parent_key = arguments["parent_key"]
            
            logger.info(f"Getting child issues for: {parent_key}")
            children = jira_service.get_child_issues(parent_key)
            
            # Add to knowledge graph
            for child in children:
                knowledge_graph_service.add_jira_issue(child)
            
            # Also add relationship to parent
            for child in children:
                knowledge_graph_service.add_relationship(
                    child["key"], parent_key, "child_of"
                )
            
            return [TextContent(
                type="text",
                text=json.dumps(children, indent=2)
            )]
        
        elif name == "search_confluence":
            query = arguments["query"]
            limit = arguments.get("limit", 10)
            
            logger.info(f"Searching Confluence: {query}")
            results = confluence_service.search_content(query, limit=limit)
            
            # Add to knowledge graph
            for page in results:
                knowledge_graph_service.add_confluence_page(page)
            
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "get_confluence_page":
            page_id = arguments["page_id"]
            
            logger.info(f"Getting Confluence page: {page_id}")
            result = confluence_service.get_page(page_id)
            
            if result:
                # Add to knowledge graph
                knowledge_graph_service.add_confluence_page(result)
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Page {page_id} not found"
                )]
        
        elif name == "get_knowledge_graph_stats":
            logger.info("Getting knowledge graph stats")
            stats = knowledge_graph_service.get_graph_stats()
            
            return [TextContent(
                type="text",
                text=json.dumps(stats, indent=2)
            )]
        
        elif name == "populate_knowledge_graph":
            logger.info("Populating knowledge graph from all sources")
            results = knowledge_graph_service.populate_from_services()
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "results": results,
                    "message": f"Added {results['jira_issues']} Jira issues and {results['confluence_pages']} Confluence pages"
                }, indent=2)
            )]
        
        elif name == "search_knowledge_graph":
            entity_type = arguments.get("entity_type")
            property_filter = arguments.get("property_filter")
            
            logger.info(f"Searching knowledge graph: type={entity_type}, filter={property_filter}")
            results = knowledge_graph_service.search_entities(
                entity_type=entity_type,
                property_filter=property_filter
            )
            
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "get_related_entities":
            entity_id = arguments["entity_id"]
            relationship_type = arguments.get("relationship_type")
            max_depth = arguments.get("max_depth", 2)
            
            logger.info(f"Getting related entities for: {entity_id}")
            results = knowledge_graph_service.get_related_entities(
                entity_id=entity_id,
                relationship_type=relationship_type,
                max_depth=max_depth
            )
            
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "create_jira_issue":
            # WRITE OPERATION - Return proposal for approval
            proposal = {
                "action": "create_jira_issue",
                "requires_approval": True,
                "parameters": arguments,
                "warning": "⚠️ This will CREATE a new Jira issue. Please review and approve.",
                "preview": {
                    "project": arguments["project_key"],
                    "summary": arguments["summary"],
                    "type": arguments.get("issue_type", "Task"),
                    "description": arguments.get("description", "")[:200] + "..."
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(proposal, indent=2)
            )]
        
        elif name == "update_jira_issue":
            # WRITE OPERATION - Return proposal for approval
            issue_key = arguments["issue_key"]
            
            # Get current state
            current = jira_service.get_issue(issue_key)
            
            proposal = {
                "action": "update_jira_issue",
                "requires_approval": True,
                "parameters": arguments,
                "warning": f"⚠️ This will UPDATE issue {issue_key}. Please review changes.",
                "current_state": current,
                "proposed_changes": {k: v for k, v in arguments.items() if k != "issue_key" and k != "approval_required"}
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(proposal, indent=2)
            )]
        
        elif name == "transition_jira_issue":
            # WRITE OPERATION - Return proposal for approval
            issue_key = arguments["issue_key"]
            transition_name = arguments["transition_name"]
            
            current = jira_service.get_issue(issue_key)
            
            proposal = {
                "action": "transition_jira_issue",
                "requires_approval": True,
                "parameters": arguments,
                "warning": f"⚠️ This will change status of {issue_key}.",
                "current_status": current.get("status") if current else "Unknown",
                "new_status": transition_name
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(proposal, indent=2)
            )]
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def main():
    """Run the MCP server"""
    logger.info("Starting Jira-Confluence MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
