"""
Knowledge Graph Visualization Tool

Provides efficient visualization of the knowledge graph using D3.js force-directed layout.
Can be run standalone or integrated with the API.

Usage:
    python -m scripts.visualize_graph                    # Uses default knowledge_graph.gpickle
    python -m scripts.visualize_graph --graphml file.graphml
    python -m scripts.visualize_graph --port 8080
"""
import networkx as nx
import json
import os
import webbrowser
import threading
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Dict, Any
import tempfile
import pickle


def load_graph(file_path: str) -> nx.Graph:
    """Load graph from various formats"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.graphml':
        return nx.read_graphml(file_path)
    elif ext == '.gpickle':
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    elif ext == '.json':
        with open(file_path, 'r') as f:
            data = json.load(f)
            return nx.node_link_graph(data)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def graph_to_d3_json(graph: nx.Graph) -> Dict[str, Any]:
    """
    Convert NetworkX graph to D3-compatible JSON format.
    
    Optimized for performance with large graphs.
    """
    nodes = []
    entity_types = set()
    
    for node_id, node_data in graph.nodes(data=True):
        entity_type = node_data.get('entity_type', 'unknown')
        entity_types.add(entity_type)
        properties = node_data.get('properties', {})
        
        nodes.append({
            "id": str(node_id),
            "entity_type": entity_type,
            "label": str(node_id),
            "description": properties.get('summary') or properties.get('title') or properties.get('description', ''),
            # Size based on connections (importance)
            "size": graph.degree(node_id) + 1
        })
    
    links = []
    for source, target, edge_data in graph.edges(data=True):
        rel_type = edge_data.get('relationship_type', edge_data.get('description', 'related'))
        links.append({
            "source": str(source),
            "target": str(target),
            "description": str(rel_type),
            "weight": edge_data.get('weight', 1)
        })
    
    return {
        "nodes": nodes,
        "links": links,
        "entity_types": list(entity_types),
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(links)
        }
    }


def create_visualization_html() -> str:
    """Create the D3.js visualization HTML with embedded styles and scripts"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knowledge Graph Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body, html {
            width: 100%;
            height: 100%;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0a0a0f;
        }
        #graph-container {
            width: 100%;
            height: 100%;
        }
        svg {
            width: 100%;
            height: 100%;
            display: block;
        }
        .node {
            cursor: grab;
        }
        .node:active {
            cursor: grabbing;
        }
        .node-label {
            font-size: 11px;
            fill: #e0e0e0;
            pointer-events: none;
            text-shadow: 0 0 3px #000;
        }
        .link {
            stroke: #444;
            stroke-opacity: 0.6;
        }
        .link-label {
            font-size: 9px;
            fill: #888;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .link:hover + .link-label,
        .link-group:hover .link-label {
            opacity: 1;
        }
        
        /* Tooltip */
        .tooltip {
            position: fixed;
            padding: 12px 16px;
            background: rgba(20, 20, 30, 0.95);
            border: 1px solid #333;
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 13px;
            pointer-events: none;
            z-index: 1000;
            max-width: 350px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            opacity: 0;
            transition: opacity 0.2s;
        }
        .tooltip.visible { opacity: 1; }
        .tooltip h4 { 
            color: #fff; 
            margin-bottom: 8px;
            font-size: 14px;
        }
        .tooltip .type-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .tooltip .description {
            color: #aaa;
            font-size: 12px;
            line-height: 1.4;
        }
        
        /* Controls panel */
        .controls {
            position: fixed;
            top: 16px;
            left: 16px;
            background: rgba(20, 20, 30, 0.9);
            border: 1px solid #333;
            border-radius: 10px;
            padding: 16px;
            color: #e0e0e0;
            z-index: 100;
            min-width: 220px;
        }
        .controls h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #fff;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 12px;
        }
        .stat-value { color: #4fc3f7; font-weight: bold; }
        
        /* Legend */
        .legend {
            position: fixed;
            top: 16px;
            right: 16px;
            background: rgba(20, 20, 30, 0.9);
            border: 1px solid #333;
            border-radius: 10px;
            padding: 16px;
            color: #e0e0e0;
            z-index: 100;
            max-height: 60vh;
            overflow-y: auto;
        }
        .legend h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #fff;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 6px 0;
            font-size: 12px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            transition: background 0.2s;
        }
        .legend-item:hover {
            background: rgba(255,255,255,0.1);
        }
        .legend-color {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid rgba(255,255,255,0.2);
        }
        .legend-item.hidden .legend-color {
            opacity: 0.3;
        }
        .legend-count {
            margin-left: auto;
            color: #666;
            font-size: 11px;
        }
        
        /* Search */
        .search-container {
            position: fixed;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 100;
        }
        .search-input {
            width: 320px;
            padding: 12px 20px;
            background: rgba(20, 20, 30, 0.95);
            border: 1px solid #333;
            border-radius: 25px;
            color: #e0e0e0;
            font-size: 14px;
            outline: none;
        }
        .search-input:focus {
            border-color: #4fc3f7;
            box-shadow: 0 0 10px rgba(79, 195, 247, 0.3);
        }
        .search-input::placeholder {
            color: #666;
        }
        
        /* Instructions */
        .instructions {
            position: fixed;
            bottom: 16px;
            right: 16px;
            background: rgba(20, 20, 30, 0.8);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 10px 14px;
            color: #888;
            font-size: 11px;
            z-index: 100;
        }
    </style>
</head>
<body>
    <div id="graph-container"></div>
    <div class="tooltip" id="tooltip"></div>
    
    <div class="controls">
        <h3>📊 Graph Stats</h3>
        <div class="stat"><span>Nodes</span><span class="stat-value" id="stat-nodes">-</span></div>
        <div class="stat"><span>Edges</span><span class="stat-value" id="stat-edges">-</span></div>
        <div class="stat"><span>Entity Types</span><span class="stat-value" id="stat-types">-</span></div>
    </div>
    
    <div class="legend" id="legend">
        <h3>🏷️ Entity Types</h3>
    </div>
    
    <div class="search-container">
        <input type="text" class="search-input" id="search" placeholder="🔍 Search nodes...">
    </div>
    
    <div class="instructions">
        Scroll to zoom • Drag nodes • Click legend to filter
    </div>
    
    <script>
        // Load graph data
        fetch('./graph_data.json')
            .then(r => r.json())
            .then(data => initGraph(data))
            .catch(err => console.error('Failed to load graph:', err));
        
        function initGraph(data) {
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            // Color scale for entity types
            const color = d3.scaleOrdinal(d3.schemeTableau10);
            
            // Update stats
            document.getElementById('stat-nodes').textContent = data.nodes.length;
            document.getElementById('stat-edges').textContent = data.links.length;
            document.getElementById('stat-types').textContent = data.entity_types.length;
            
            // Build legend
            const legend = document.getElementById('legend');
            const typeVisibility = {};
            const typeCounts = {};
            
            data.nodes.forEach(n => {
                typeCounts[n.entity_type] = (typeCounts[n.entity_type] || 0) + 1;
            });
            
            data.entity_types.forEach(type => {
                typeVisibility[type] = true;
                const item = document.createElement('div');
                item.className = 'legend-item';
                item.innerHTML = `
                    <span class="legend-color" style="background-color: ${color(type)}"></span>
                    <span>${type}</span>
                    <span class="legend-count">${typeCounts[type] || 0}</span>
                `;
                item.onclick = () => {
                    typeVisibility[type] = !typeVisibility[type];
                    item.classList.toggle('hidden', !typeVisibility[type]);
                    updateVisibility();
                };
                legend.appendChild(item);
            });
            
            // Create SVG
            const svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Add zoom behavior
            const g = svg.append('g');
            const zoom = d3.zoom()
                .scaleExtent([0.1, 8])
                .on('zoom', (event) => g.attr('transform', event.transform));
            svg.call(zoom);
            
            // Create simulation with tuned parameters for performance
            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.links).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-200).distanceMax(400))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.size) * 5 + 10))
                .alphaDecay(0.02)  // Faster settling
                .velocityDecay(0.4);
            
            // Draw links
            const linkGroup = g.append('g').attr('class', 'links');
            const link = linkGroup.selectAll('line')
                .data(data.links)
                .enter().append('line')
                .attr('class', 'link')
                .attr('stroke-width', d => Math.max(1, Math.sqrt(d.weight)));
            
            // Draw nodes
            const nodeGroup = g.append('g').attr('class', 'nodes');
            const node = nodeGroup.selectAll('circle')
                .data(data.nodes)
                .enter().append('circle')
                .attr('class', 'node')
                .attr('r', d => Math.sqrt(d.size) * 4 + 5)
                .attr('fill', d => color(d.entity_type))
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));
            
            // Draw labels (only for nodes with many connections for performance)
            const labelGroup = g.append('g').attr('class', 'labels');
            const label = labelGroup.selectAll('text')
                .data(data.nodes.filter(d => d.size >= 2))
                .enter().append('text')
                .attr('class', 'node-label')
                .attr('dy', d => Math.sqrt(d.size) * 4 + 15)
                .attr('text-anchor', 'middle')
                .text(d => d.label.length > 20 ? d.label.substring(0, 18) + '...' : d.label);
            
            // Tooltip handling
            const tooltip = document.getElementById('tooltip');
            
            node.on('mouseover', (event, d) => {
                tooltip.innerHTML = `
                    <h4>${d.label}</h4>
                    <span class="type-badge" style="background: ${color(d.entity_type)}40; color: ${color(d.entity_type)}">${d.entity_type}</span>
                    ${d.description ? `<div class="description">${d.description}</div>` : ''}
                `;
                tooltip.style.left = event.pageX + 15 + 'px';
                tooltip.style.top = event.pageY - 10 + 'px';
                tooltip.classList.add('visible');
            })
            .on('mouseout', () => tooltip.classList.remove('visible'));
            
            // Tick function
            simulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
                
                label
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
            });
            
            // Drag functions
            function dragstarted(event) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }
            
            function dragged(event) {
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }
            
            function dragended(event) {
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }
            
            // Search functionality
            const searchInput = document.getElementById('search');
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                node.attr('opacity', d => {
                    const match = !query || d.label.toLowerCase().includes(query) || 
                                  d.entity_type.toLowerCase().includes(query);
                    return match ? 1 : 0.1;
                });
                label.attr('opacity', d => {
                    const match = !query || d.label.toLowerCase().includes(query);
                    return match ? 1 : 0.1;
                });
                link.attr('opacity', d => {
                    if (!query) return 1;
                    const srcMatch = d.source.label.toLowerCase().includes(query);
                    const tgtMatch = d.target.label.toLowerCase().includes(query);
                    return srcMatch || tgtMatch ? 1 : 0.05;
                });
            });
            
            // Visibility toggle from legend
            function updateVisibility() {
                node.attr('display', d => typeVisibility[d.entity_type] ? 'block' : 'none');
                label.attr('display', d => typeVisibility[d.entity_type] ? 'block' : 'none');
                link.attr('display', d => {
                    return typeVisibility[d.source.entity_type] && typeVisibility[d.target.entity_type] ? 'block' : 'none';
                });
            }
            
            // Initial zoom to fit
            const initialScale = Math.min(width / 1200, height / 800, 1);
            svg.call(zoom.transform, d3.zoomIdentity
                .translate(width/2, height/2)
                .scale(initialScale)
                .translate(-width/2, -height/2));
        }
    </script>
</body>
</html>
'''


def run_visualization_server(html_path: str, json_path: str, port: int = 8080, open_browser: bool = True):
    """Run a simple HTTP server for the visualization"""
    serve_dir = os.path.dirname(os.path.abspath(html_path))
    
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_dir, **kwargs)
        
        def log_message(self, format, *args):
            # Suppress HTTP logging
            pass
    
    server = HTTPServer(('localhost', port), Handler)
    
    url = f'http://localhost:{port}/{os.path.basename(html_path)}'
    print(f"🌐 Knowledge Graph Visualization: {url}")
    print("   Press Ctrl+C to stop the server")
    
    if open_browser:
        def open_delayed():
            import time
            time.sleep(0.5)
            webbrowser.open(url)
        threading.Thread(target=open_delayed, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.shutdown()


def visualize_graph(
    graph_file: Optional[str] = None, 
    output_dir: Optional[str] = None,
    port: int = 8080,
    open_browser: bool = True
):
    """
    Main visualization function.
    
    Args:
        graph_file: Path to graph file (.gpickle, .graphml, or .json)
        output_dir: Directory for output files (default: temp directory)
        port: HTTP server port
        open_browser: Whether to open browser automatically
    """
    # Default to knowledge graph
    if graph_file is None:
        graph_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'knowledge_graph.gpickle'
        )
    
    if not os.path.exists(graph_file):
        print(f"❌ Graph file not found: {graph_file}")
        return
    
    print(f"📊 Loading graph from: {graph_file}")
    graph = load_graph(graph_file)
    print(f"   Nodes: {graph.number_of_nodes()}, Edges: {graph.number_of_edges()}")
    
    # Convert to D3 format
    d3_data = graph_to_d3_json(graph)
    
    # Setup output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix='graph_viz_')
    os.makedirs(output_dir, exist_ok=True)
    
    # Write files
    html_path = os.path.join(output_dir, 'index.html')
    json_path = os.path.join(output_dir, 'graph_data.json')
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(create_visualization_html())
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(d3_data, f)
    
    print(f"✅ Visualization files created in: {output_dir}")
    
    # Start server
    run_visualization_server(html_path, json_path, port, open_browser)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Knowledge Graph Visualization')
    parser.add_argument('--graph', '-g', type=str, help='Path to graph file (.gpickle, .graphml, or .json)')
    parser.add_argument('--output', '-o', type=str, help='Output directory for HTML files')
    parser.add_argument('--port', '-p', type=int, default=8080, help='HTTP server port (default: 8080)')
    parser.add_argument('--no-browser', action='store_true', help="Don't open browser automatically")
    
    args = parser.parse_args()
    
    visualize_graph(
        graph_file=args.graph,
        output_dir=args.output,
        port=args.port,
        open_browser=not args.no_browser
    )
