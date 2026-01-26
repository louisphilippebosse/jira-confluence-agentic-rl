# Knowledge Graph RAG Guide

This application uses NetworkX to build a knowledge graph that connects Jira issues, Confluence pages, users, and other entities. This enables **Retrieval Augmented Generation (RAG)** for more contextual and accurate AI responses.

## What is Knowledge Graph RAG?

Traditional RAG retrieves documents based on similarity. Knowledge Graph RAG goes further by:

1. **Building Relationships**: Connects entities (issues, users, documents) with meaningful relationships
2. **Graph Traversal**: Finds related information by following connections
3. **Context Enrichment**: Provides the AI with structured, relationship-aware context
4. **Network Analysis**: Identifies central entities, bottlenecks, and patterns

## Architecture

```
User Query
    ↓
Knowledge Graph Query
    ↓
[Nodes: Issues, Pages, Users]
[Edges: assigned_to, relates_to, documented_in]
    ↓
Context Extraction
    ↓
LLM (with enriched context)
    ↓
Enhanced Response
```

## Features

### 1. **Automatic Entity Extraction**

When you interact with Jira or Confluence, entities are automatically added to the knowledge graph:

- **Jira Issues**: Issue key, summary, status, assignee, etc.
- **Confluence Pages**: Page ID, title, space, content
- **Users**: User names and their assignments
- **Relationships**: "assigned_to", "depends_on", "documented_in"

### 2. **Relationship Mapping**

The system automatically creates relationships:

```python
JIRA-123 --[assigned_to]--> User:john.doe
JIRA-123 --[documented_in]--> Confluence:45678
JIRA-456 --[blocks]--> JIRA-123
```

### 3. **Graph Queries**

Query the knowledge graph through the API:

```bash
# Get entity details
curl http://localhost:8000/api/kg/entity/JIRA-123

# Find related entities
curl http://localhost:8000/api/kg/entity/JIRA-123/related

# Get graph statistics
curl http://localhost:8000/api/kg/stats

# Find path between entities
curl http://localhost:8000/api/kg/path/JIRA-123/JIRA-456

# Get most central entities
curl http://localhost:8000/api/kg/central
```

### 4. **Network Analysis**

The knowledge graph provides insights through network analysis:

- **PageRank**: Identifies most important entities
- **Shortest Path**: Finds connections between entities
- **Clustering**: Discovers related groups of work
- **Centrality**: Identifies key people or issues

## Configuration

Enable/disable knowledge graph in `.env`:

```bash
# Enable knowledge graph
ENABLE_KNOWLEDGE_GRAPH=true

# Set storage location
KNOWLEDGE_GRAPH_PATH=./data/knowledge_graph.gpickle
```

## API Endpoints

### Get Statistics

```bash
GET /api/kg/stats
```

Response:
```json
{
  "enabled": true,
  "total_nodes": 150,
  "total_edges": 320,
  "entity_types": {
    "jira_issue": 100,
    "confluence_page": 30,
    "user": 20
  }
}
```

### Get Entity

```bash
GET /api/kg/entity/{entity_id}
```

Response:
```json
{
  "id": "JIRA-123",
  "type": "jira_issue",
  "properties": {
    "summary": "Fix login bug",
    "status": "In Progress",
    "assignee": "john.doe"
  },
  "updated_at": "2026-01-26T10:30:00"
}
```

### Get Related Entities

```bash
GET /api/kg/entity/{entity_id}/related?relationship_type=assigned_to
```

Response:
```json
{
  "entity_id": "JIRA-123",
  "related": [
    {
      "id": "user:john.doe",
      "type": "user",
      "relationship": "assigned_to",
      "properties": {
        "name": "john.doe"
      }
    }
  ]
}
```

### Search Entities

```bash
POST /api/kg/search
Content-Type: application/json

{
  "entity_type": "jira_issue",
  "property_filter": {
    "status": "In Progress"
  }
}
```

### Find Path

```bash
GET /api/kg/path/{source_id}/{target_id}
```

Response:
```json
{
  "path": ["JIRA-123", "user:john.doe", "JIRA-456"],
  "length": 2
}
```

### Get Central Entities

```bash
GET /api/kg/central?limit=5
```

Response:
```json
{
  "central_entities": [
    {"id": "user:john.doe", "score": 0.0456},
    {"id": "JIRA-123", "score": 0.0423},
    {"id": "JIRA-789", "score": 0.0401}
  ]
}
```

## Use Cases

### 1. **Find Related Work**

"Show me all issues related to JIRA-123"
- Traverses the graph to find connected issues
- Includes issues assigned to same person
- Finds documentation about the same topic

### 2. **Identify Bottlenecks**

"Who are the most central people in the project?"
- Uses PageRank to find key contributors
- Identifies dependencies
- Suggests workload distribution

### 3. **Impact Analysis**

"What will be affected if we change JIRA-123?"
- Finds all dependent issues
- Identifies related documentation
- Shows affected team members

### 4. **Knowledge Discovery**

"Find documentation related to this issue"
- Searches Confluence pages
- Maps relationships
- Provides relevant context

## Advanced Usage

### Custom Relationships

You can add custom relationships programmatically:

```python
from app.services.knowledge_graph_service import knowledge_graph_service

# Add custom relationship
knowledge_graph_service.add_relationship(
    source_id="JIRA-123",
    target_id="JIRA-456",
    relationship_type="depends_on",
    properties={"weight": 1.0}
)
```

### Graph Algorithms

NetworkX provides many algorithms:

```python
import networkx as nx
from app.services.knowledge_graph_service import knowledge_graph_service

graph = knowledge_graph_service.graph

# Community detection
communities = nx.community.greedy_modularity_communities(graph.to_undirected())

# Betweenness centrality
centrality = nx.betweenness_centrality(graph)

# Strongly connected components
components = list(nx.strongly_connected_components(graph))
```

### Export Graph

Export for visualization:

```python
import json
import networkx as nx

# Export to JSON
graph_data = nx.node_link_data(graph)
with open('graph.json', 'w') as f:
    json.dump(graph_data, f)

# Export to GraphML (for Gephi, Cytoscape)
nx.write_graphml(graph, 'graph.graphml')

# Export to DOT (for Graphviz)
nx.drawing.nx_pydot.write_dot(graph, 'graph.dot')
```

## Visualization

While the application doesn't include built-in visualization, you can:

1. **Export the graph** (as shown above)
2. **Use external tools**:
   - **Gephi**: https://gephi.org/
   - **Cytoscape**: https://cytoscape.org/
   - **vis.js**: For web-based visualization
   - **D3.js**: For custom interactive graphs

3. **Simple Python visualization**:

```python
import matplotlib.pyplot as plt
import networkx as nx

graph = knowledge_graph_service.graph
pos = nx.spring_layout(graph)
nx.draw(graph, pos, with_labels=True, node_color='lightblue', 
        node_size=500, font_size=8, arrows=True)
plt.savefig('knowledge_graph.png')
```

## Performance Considerations

- **Graph Size**: NetworkX handles 10,000+ nodes efficiently
- **Persistence**: Graph is saved after each update
- **Memory**: Loaded in memory for fast queries
- **Scalability**: For > 1M nodes, consider Neo4j or other graph databases

## Benefits

1. **Better Context**: AI gets relationship-aware information
2. **Faster Queries**: Graph traversal is efficient
3. **Insights**: Network analysis reveals hidden patterns
4. **Completeness**: No information is isolated
5. **Explainability**: Relationships make AI responses more transparent

## Limitations

- **In-Memory**: Current implementation keeps graph in memory
- **Single Instance**: Not designed for distributed systems
- **No ACID**: Simple persistence, not transactional
- **No Auth**: Entity-level access control not implemented

For production systems with millions of entities, consider:
- **Neo4j**: Full-featured graph database
- **Amazon Neptune**: Managed graph database
- **ArangoDB**: Multi-model database with graph support

## Resources

- NetworkX Documentation: https://networkx.org/
- Graph Theory Basics: https://en.wikipedia.org/wiki/Graph_theory
- RAG with Knowledge Graphs: https://arxiv.org/abs/2312.10997
