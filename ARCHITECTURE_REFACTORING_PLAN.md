# Architecture Refactoring Plan

## ✅ IMPLEMENTATION STATUS

### Phase 1: Tool Abstraction Layer - COMPLETE ✅
- [x] Created `app/services/tools/base.py` - BaseTool interface
- [x] Created `app/services/tools/tool_registry.py` - Tool registration
- [x] Created `app/services/tools/tool_router.py` - Intent-based routing

### Phase 2: Tool Implementations - COMPLETE ✅
- [x] Created `app/services/tools/jira/` package
  - [x] `jira_tool.py` - Implements BaseTool
  - [x] `jira_intent.py` - Jira intent detection
- [x] Created `app/services/tools/confluence/` package
  - [x] `confluence_tool.py` - Implements BaseTool
  - [x] `confluence_intent.py` - Confluence intent detection
- [x] Created `app/services/tools/web/` package
  - [x] `web_tool.py` - Implements BaseTool
  - [x] `web_intent.py` - Web intent detection
- [x] Created `app/services/tools/knowledge_graph/` package
  - [x] `kg_tool.py` - Implements BaseTool
  - [x] `kg_intent.py` - KG intent detection

### Phase 3: Intelligence Layer - COMPLETE ✅
- [x] Created `app/services/intelligence/intent_classifier.py`

### Phase 4: New Orchestrator - COMPLETE ✅
- [x] Created `app/services/core/agent_orchestrator.py` - Tool-agnostic orchestrator

### Phase 5: API Migration & Cleanup - COMPLETE ✅
- [x] Added `orchestrator_mode` config setting for gradual migration
- [x] Updated `app/api/chat.py` to dynamically select orchestrator
- [x] Fixed ai_agent_service imports (removed duplicate dependency)
- [x] Deleted empty `app/services/integrations/jira/` folder (duplicate of intelligence/)

### Phase 6: Remaining Work - TODO 🔄
- [ ] Move remaining Jira-specific code from `ai_agent_service.py` to tools/jira/
- [ ] Move remaining Confluence-specific code to tools/confluence/
- [ ] Move orchestration/mcp_operations.py functionality to tool-specific files
- [ ] Full test suite validation
- [ ] Production deployment with orchestrator_mode="new"

---

## Executive Summary

This document outlines a comprehensive refactoring plan to restructure the codebase following **SOLID principles**, **Anthropic's AI agent best practices**, and **semantic organization**. The goal is to make `AIAgentService` tool-agnostic and properly delegate responsibilities to specialized modules.

---

## Current Problems Identified

### 1. **AIAgentService is a "God Class"** (1736 lines)
- Contains Jira-specific logic (JQL building, child issue queries, status parsing)
- Contains Confluence-specific logic
- Contains web search logic
- Mixes routing logic with business logic
- Violates **Single Responsibility Principle**

### 2. **Scattered Jira Code Across Multiple Folders**
```
❌ Current scattered structure:
├── services/
│   ├── core/
│   │   └── ai_agent_service.py          # Has Jira-specific code
│   ├── integrations/
│   │   ├── atlassian/
│   │   │   ├── jira/
│   │   │   │   └── jira_service.py      # Jira API calls
│   │   │   └── atlassian_mcp_client.py  # MCP for Jira+Confluence
│   │   └── jira/
│   │       └── jira_query_builder.py    # Duplicate! Empty shell
│   ├── orchestration/
│   │   ├── jira_write_service.py        # Should be with Jira!
│   │   ├── mcp_operations.py            # Has Jira+Confluence code
│   │   └── search_orchestrator.py       # Has Jira-specific search
│   └── intelligence/
│       └── jira_query_builder.py        # The real implementation
```

### 3. **Semantic Confusion**
- `orchestration/` contains Jira-specific code (not orchestration)
- `intelligence/` has `jira_query_builder.py` (should be with Jira)
- Duplicate `jira_query_builder.py` in two locations
- `mcp_operations` talks about Jira/Confluence but lives in orchestration
- `skill_orchestrator` not in `orchestration/` folder

### 4. **Violations of SOLID Principles**
- **S**ingle Responsibility: `AIAgentService` does routing, Jira logic, Confluence logic, web search, and response generation
- **O**pen/Closed: Adding a new integration requires modifying `AIAgentService`
- **L**iskov Substitution: No common interface for data sources
- **I**nterface Segregation: No clear contracts between services
- **D**ependency Inversion: Hard-coded dependencies everywhere

---

## Proposed Architecture

### High-Level Design (Anthropic AI Agent Best Practices)

Following Anthropic's recommendations for AI agent architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI AGENT CORE                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  AgentOrchestrator (formerly AIAgentService)                ││
│  │  - Tool-agnostic routing                                     ││
│  │  - Conversation management                                   ││
│  │  - LLM invocation                                            ││
│  │  - Delegates ALL tool-specific logic                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TOOL ABSTRACTION LAYER                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐│
│  │  ToolRegistry │  │  ToolRouter   │  │  IntentClassifier     ││
│  │  - Register   │  │  - Route by   │  │  - Classify user      ││
│  │    tools      │  │    intent     │  │    intent             ││
│  │  - Discover   │  │  - Fallback   │  │  - Multi-tool         ││
│  │    skills     │  │    strategies │  │    detection          ││
│  └───────────────┘  └───────────────┘  └───────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TOOL IMPLEMENTATIONS                        │
│  ┌──────────────────────────────────────────────────────────────┐
│  │                     tools/                                    │
│  │  ├── jira/                    # All Jira-related code        │
│  │  │   ├── __init__.py                                         │
│  │  │   ├── jira_tool.py         # Implements BaseTool          │
│  │  │   ├── jira_service.py      # API calls                    │
│  │  │   ├── jira_query_builder.py# JQL construction             │
│  │  │   ├── jira_write_service.py# Create/Update operations     │
│  │  │   └── jira_mcp_client.py   # MCP integration              │
│  │  │                                                           │
│  │  ├── confluence/              # All Confluence-related code  │
│  │  │   ├── __init__.py                                         │
│  │  │   ├── confluence_tool.py   # Implements BaseTool          │
│  │  │   ├── confluence_service.py# API calls                    │
│  │  │   └── confluence_mcp_client.py                            │
│  │  │                                                           │
│  │  ├── web/                     # Web search                   │
│  │  │   ├── __init__.py                                         │
│  │  │   ├── web_tool.py          # Implements BaseTool          │
│  │  │   └── web_search_service.py                               │
│  │  │                                                           │
│  │  ├── knowledge_graph/         # Knowledge Graph operations   │
│  │  │   ├── __init__.py                                         │
│  │  │   ├── kg_tool.py           # Implements BaseTool          │
│  │  │   ├── kg_service.py                                       │
│  │  │   └── kg_query_service.py                                 │
│  │  │                                                           │
│  │  └── base.py                  # BaseTool interface           │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                         │
│  ┌──────────────────────────────────────────────────────────────┐
│  │                  orchestration/                               │
│  │  ├── search_orchestrator.py   # Multi-tool search            │
│  │  ├── agentic_orchestrator.py  # Plan→Execute→Reflect loop    │
│  │  ├── parallel_executor.py     # Parallel tool execution      │
│  │  └── clarification_service.py # User clarification           │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INTELLIGENCE LAYER                          │
│  ┌──────────────────────────────────────────────────────────────┐
│  │                  intelligence/                                │
│  │  ├── intent_classifier.py     # Route to correct tool        │
│  │  ├── query_analyzer.py        # Analyze query complexity     │
│  │  ├── result_ranker.py         # Rank/filter results          │
│  │  ├── entity_extractor.py      # Extract entities from text   │
│  │  └── agentic_planner.py       # Plan multi-step execution    │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

---

## New Folder Structure

```
app/
├── services/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent_orchestrator.py      # RENAMED: Tool-agnostic orchestrator
│   │   ├── skill_middleware.py        # Skills integration
│   │   ├── skill_registry.py          # Skill registration
│   │   └── thinking_stream.py         # Thinking updates
│   │
│   ├── tools/                          # NEW: All tool implementations
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseTool interface
│   │   ├── tool_registry.py           # Tool registration & discovery
│   │   ├── tool_router.py             # Route by intent
│   │   │
│   │   ├── jira/                      # All Jira code in ONE place
│   │   │   ├── __init__.py
│   │   │   ├── jira_tool.py           # Implements BaseTool
│   │   │   ├── jira_service.py        # MOVED from integrations/atlassian/jira
│   │   │   ├── jira_query_builder.py  # MOVED & MERGED from intelligence/
│   │   │   ├── jira_write_service.py  # MOVED from orchestration/
│   │   │   ├── jira_mcp_client.py     # Extracted from mcp_operations
│   │   │   └── jira_intent.py         # Jira-specific intent detection
│   │   │
│   │   ├── confluence/                # All Confluence code in ONE place
│   │   │   ├── __init__.py
│   │   │   ├── confluence_tool.py     # Implements BaseTool
│   │   │   ├── confluence_service.py  # MOVED from integrations/atlassian/confluence
│   │   │   ├── confluence_mcp_client.py # Extracted from mcp_operations
│   │   │   └── confluence_intent.py   # Confluence-specific intent detection
│   │   │
│   │   ├── web/                       # Web search
│   │   │   ├── __init__.py
│   │   │   ├── web_tool.py            # Implements BaseTool
│   │   │   ├── web_search_service.py  # MOVED from integrations/web
│   │   │   └── web_intent.py
│   │   │
│   │   └── knowledge_graph/           # Knowledge Graph
│   │       ├── __init__.py
│   │       ├── kg_tool.py             # Implements BaseTool
│   │       ├── kg_service.py          # MOVED from data/
│   │       └── kg_query_service.py    # MOVED from knowledge/
│   │
│   ├── orchestration/                 # TRUE orchestration logic
│   │   ├── __init__.py
│   │   ├── search_orchestrator.py     # Multi-tool search (tool-agnostic)
│   │   ├── agentic_orchestrator.py    # Plan→Execute→Reflect
│   │   ├── parallel_executor.py       # Parallel tool execution
│   │   └── clarification_service.py   # User clarification flows
│   │
│   ├── intelligence/                  # AI/ML intelligence (tool-agnostic)
│   │   ├── __init__.py
│   │   ├── intent_classifier.py       # Classify user intent → tool
│   │   ├── query_analyzer.py          # Analyze query complexity
│   │   ├── result_ranker.py           # Rank results
│   │   ├── entity_extractor.py        # Extract entities
│   │   └── agentic_planner.py         # Plan execution steps
│   │
│   └── data/                          # Pure data services
│       ├── __init__.py
│       └── rl_service.py              # Reinforcement learning
│
├── models/                            # Data models (unchanged)
└── api/                               # API endpoints (unchanged)
```

---

## BaseTool Interface (SOLID: Interface Segregation)

```python
# app/services/tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ToolResult:
    """Standard result from any tool"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseTool(ABC):
    """Base interface for all tools (Jira, Confluence, Web, KG)"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier (e.g., 'jira', 'confluence')"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM routing"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of actions this tool can perform"""
        pass
    
    @abstractmethod
    def can_handle(self, intent: str, message: str) -> float:
        """
        Return confidence score (0-1) that this tool can handle the request.
        Enables intelligent routing without hard-coding in orchestrator.
        """
        pass
    
    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute an action with given parameters"""
        pass
    
    @abstractmethod
    def get_actions(self) -> Dict[str, Dict[str, Any]]:
        """Return available actions with their parameter schemas"""
        pass
```

---

## JiraTool Implementation Example

```python
# app/services/tools/jira/jira_tool.py
from typing import Dict, Any, List
from ..base import BaseTool, ToolResult
from .jira_service import JiraService
from .jira_query_builder import JiraQueryBuilder
from .jira_write_service import JiraWriteService
from .jira_intent import JiraIntentDetector

class JiraTool(BaseTool):
    """Jira tool implementation - all Jira logic encapsulated here"""
    
    def __init__(self, llm=None, mcp_enabled: bool = False):
        self.jira_service = JiraService()
        self.query_builder = JiraQueryBuilder(llm)
        self.write_service = JiraWriteService(llm)
        self.intent_detector = JiraIntentDetector()
        self.mcp_enabled = mcp_enabled
    
    @property
    def name(self) -> str:
        return "jira"
    
    @property
    def description(self) -> str:
        return "Search and manage Jira issues, epics, stories, bugs, and tasks"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "search_issues",
            "get_issue",
            "get_child_issues",
            "create_issue",
            "update_issue",
            "build_jql"
        ]
    
    def can_handle(self, intent: str, message: str) -> float:
        """Use JiraIntentDetector to score relevance"""
        return self.intent_detector.score(intent, message)
    
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute Jira action"""
        try:
            if action == "search_issues":
                results = await self._search_issues(params)
                return ToolResult(success=True, data=results)
            elif action == "get_issue":
                result = await self._get_issue(params.get("issue_key"))
                return ToolResult(success=True, data=result)
            elif action == "get_child_issues":
                results = self._get_child_issues(params.get("parent_key"))
                return ToolResult(success=True, data=results)
            elif action == "build_jql":
                jql = self.query_builder.build_intelligent_query(params.get("message"))
                return ToolResult(success=True, data={"jql": jql})
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _search_issues(self, params: Dict) -> List[Dict]:
        """Search Jira issues - encapsulates all search logic"""
        message = params.get("message", "")
        jql = params.get("jql") or self.query_builder.build_intelligent_query(message)
        
        # Try MCP first if enabled
        if self.mcp_enabled:
            results = await self.mcp_client.search(jql)
            if results:
                return results
        
        # Fallback to direct API
        return self.jira_service.search_issues(jql, max_results=params.get("max_results", 20))
```

---

## Tool-Agnostic AgentOrchestrator

```python
# app/services/core/agent_orchestrator.py
from typing import Dict, Any, List, Optional
from ..tools.tool_registry import ToolRegistry
from ..tools.tool_router import ToolRouter
from ..intelligence.intent_classifier import IntentClassifier

class AgentOrchestrator:
    """
    Tool-agnostic AI agent orchestrator.
    
    Responsibilities:
    - Conversation management
    - Intent classification
    - Tool routing (via ToolRouter)
    - Response synthesis
    
    Does NOT contain any tool-specific logic.
    """
    
    def __init__(self, llm):
        self.llm = llm
        self.tool_registry = ToolRegistry()
        self.tool_router = ToolRouter(self.tool_registry)
        self.intent_classifier = IntentClassifier(llm)
        
        # Tools register themselves
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools"""
        from ..tools.jira import JiraTool
        from ..tools.confluence import ConfluenceTool
        from ..tools.web import WebTool
        from ..tools.knowledge_graph import KGTool
        
        self.tool_registry.register(JiraTool(self.llm))
        self.tool_registry.register(ConfluenceTool(self.llm))
        self.tool_registry.register(WebTool())
        self.tool_registry.register(KGTool())
    
    async def chat(self, message: str, session_id: str, 
                   conversation_history: List = None,
                   context_modes: List[str] = None) -> str:
        """
        Process chat message using tool-agnostic routing.
        
        1. Classify intent
        2. Route to appropriate tool(s)
        3. Execute and collect results
        4. Synthesize response
        """
        # Step 1: Classify intent
        intent = await self.intent_classifier.classify(message, conversation_history)
        
        # Step 2: Route to tools (may be multiple for complex queries)
        if context_modes:
            # User explicitly selected tools
            tools = [self.tool_registry.get(mode) for mode in context_modes]
        else:
            # Auto-route based on intent
            tools = self.tool_router.route(intent, message)
        
        # Step 3: Execute tools
        results = {}
        for tool in tools:
            if tool:
                result = await tool.execute(intent.action, {
                    "message": message,
                    "context": conversation_history
                })
                results[tool.name] = result
        
        # Step 4: Synthesize response
        return self._synthesize_response(message, results, conversation_history)
    
    def _synthesize_response(self, message: str, results: Dict, history: List) -> str:
        """Use LLM to synthesize response from tool results"""
        # Build context from results
        context_parts = []
        for tool_name, result in results.items():
            if result.success:
                context_parts.append(f"**{tool_name.title()} Results:**\n{result.data}")
        
        prompt = f"""User asked: {message}

{chr(10).join(context_parts)}

Synthesize a helpful response based on the data above.
Use markdown formatting. Be conversational but factual."""
        
        response = self.llm.invoke(prompt)
        return response.content
```

---

## Migration Steps

### Phase 1: Create Tool Abstraction (Week 1)
1. Create `app/services/tools/base.py` with `BaseTool` interface
2. Create `app/services/tools/tool_registry.py`
3. Create `app/services/tools/tool_router.py`
4. Write tests for tool abstraction

### Phase 2: Consolidate Jira Code (Week 1-2)
1. Create `app/services/tools/jira/` folder
2. Move `jira_service.py` from `integrations/atlassian/jira/`
3. Merge `jira_query_builder.py` (delete the empty one in `integrations/jira/`)
4. Move `jira_write_service.py` from `orchestration/`
5. Extract Jira-specific MCP code from `mcp_operations.py`
6. Create `JiraTool` implementing `BaseTool`
7. Create `JiraIntentDetector` for intent scoring
8. Write tests

### Phase 3: Consolidate Confluence Code (Week 2)
1. Create `app/services/tools/confluence/` folder
2. Move `confluence_service.py` from `integrations/atlassian/confluence/`
3. Extract Confluence-specific MCP code
4. Create `ConfluenceTool` implementing `BaseTool`
5. Create `ConfluenceIntentDetector`
6. Write tests

### Phase 4: Consolidate Web & KG Tools (Week 2)
1. Create `app/services/tools/web/` and `knowledge_graph/`
2. Move relevant services
3. Create `WebTool` and `KGTool`
4. Write tests

### Phase 5: Refactor AgentOrchestrator (Week 3)
1. Rename `ai_agent_service.py` → `agent_orchestrator.py`
2. Remove ALL tool-specific code (Jira, Confluence, web)
3. Implement tool-agnostic routing
4. Use `ToolRouter` for intent-based routing
5. Keep only: LLM initialization, conversation management, response synthesis
6. Write tests

### Phase 6: Clean Up Orchestration Layer (Week 3)
1. Make `search_orchestrator.py` tool-agnostic (use `BaseTool` interface)
2. Keep `clarification_service.py` (already generic)
3. Remove `mcp_operations.py` (split into tool-specific clients)
4. Write tests

### Phase 7: Clean Up & Delete Old Files (Week 4)
1. Delete empty/duplicate files
2. Update all imports across codebase
3. Update `__init__.py` files
4. Run full test suite
5. Update documentation

---

## Files to Delete After Migration

```
# Duplicates / Empty shells
app/services/integrations/jira/jira_query_builder.py  # Empty shell

# Merged into tool folders
app/services/integrations/atlassian/jira/             # → tools/jira/
app/services/integrations/atlassian/confluence/       # → tools/confluence/
app/services/orchestration/jira_write_service.py      # → tools/jira/
app/services/orchestration/mcp_operations.py          # Split into tool-specific clients
app/services/intelligence/jira_query_builder.py       # → tools/jira/
app/services/knowledge/kg_query_service.py            # → tools/knowledge_graph/
```

---

## Benefits of New Architecture

### 1. **SOLID Compliance**
- **S**: Each class has one responsibility
- **O**: Add new tools without modifying orchestrator
- **L**: All tools are substitutable via `BaseTool`
- **I**: Clean `BaseTool` interface
- **D**: Orchestrator depends on abstractions, not implementations

### 2. **Semantic Organization**
- All Jira code in `tools/jira/`
- All Confluence code in `tools/confluence/`
- Easy to find and modify related code

### 3. **Anthropic Best Practices**
- Clear tool abstraction layer
- Intent-based routing
- Skills integration via middleware
- Agentic planning separated from execution

### 4. **Maintainability**
- `AgentOrchestrator` reduced from 1736 lines to ~200 lines
- New integrations don't require core changes
- Easier testing with mocked tools

### 5. **Extensibility**
- Add new tools by implementing `BaseTool`
- Register with `ToolRegistry`
- Automatic routing integration

---

## Immediate Action Items

1. **Create base tool interface** (`tools/base.py`)
2. **Create JiraTool** as first implementation
3. **Extract Jira-specific code** from `ai_agent_service.py`
4. **Test JiraTool** in isolation
5. **Iterate** for other tools

Start with Phase 1 and Phase 2 - they provide the most value with lowest risk.
