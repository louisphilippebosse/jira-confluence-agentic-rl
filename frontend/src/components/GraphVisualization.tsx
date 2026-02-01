import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

interface NodeProperties {
  // Jira issue fields
  summary?: string;
  status?: string;
  priority?: string;
  assignee?: string;
  reporter?: string;
  created?: string;
  updated?: string;
  issue_type?: string;
  description?: string;
  labels?: string[];
  components?: string[];
  epic_key?: string;
  parent?: string;
  project_key?: string;
  has_subtasks?: boolean;
  // Confluence fields
  space_key?: string;
  author?: string;
  last_modified?: string;
  // User fields
  displayName?: string;
  email?: string;
  // Project fields
  key?: string;
  name?: string;
  // Generic
  [key: string]: unknown;
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  title?: string;
  properties?: NodeProperties;
}

interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphVisualizationProps {
  maxNodes?: number;
  highlightNodeId?: string | null;
  filterType?: string | null;
  searchQuery?: string;
  onNodeSelect?: (node: GraphNode | null) => void;
  onTypeFilter?: (type: string | null) => void;
}

// Color scheme for different entity types
const typeColors: Record<string, string> = {
  jira_issue: '#0052cc',
  project: '#00875a',
  user: '#6554c0',
  confluence_page: '#ff5630',
  confluence_space: '#ff8b00',
  epic: '#36b37e',
  story: '#4b9cff',
  bug: '#de350b',
  task: '#00b8d9',
  subtask: '#8777d9',
  idea: '#ff991f',         // Product Discovery / Ideas - orange-gold
  initiative: '#403294',   // Strategic initiatives - deep purple
  feature: '#00c7e6',      // Features - cyan
  improvement: '#57d9a3',  // Improvements - mint green
  label: '#00a3bf',
  component: '#5243aa',
  unknown: '#97a0af',
};

// Default color for types not in the map
const getTypeColor = (type: string): string => {
  return typeColors[type] || typeColors.unknown;
};

// Infer better type from node ID pattern
function inferNodeType(node: GraphNode): string {
  if (node.type && node.type !== 'unknown') {
    return node.type;
  }
  
  const id = node.id;
  
  // Check for Jira issue pattern (PROJ-123)
  if (/^[A-Z]+-\d+$/.test(id)) {
    // Could be subtask, task, story, etc - but without more info, mark as jira_issue
    return 'jira_issue';
  }
  
  // Check for confluence page
  if (id.startsWith('confluence:')) {
    return 'confluence_page';
  }
  
  // Check for user
  if (id.startsWith('user:')) {
    return 'user';
  }
  
  // Check for space
  if (id.startsWith('space:')) {
    return 'confluence_space';
  }
  
  // Check for project
  if (id.startsWith('project:')) {
    return 'project';
  }
  
  // Check for label
  if (id.startsWith('label:')) {
    return 'label';
  }
  
  // Check for component
  if (id.startsWith('component:')) {
    return 'component';
  }
  
  return node.type || 'unknown';
}

// Get display name for node
function getDisplayName(node: GraphNode): string {
  // For prefixed IDs, remove the prefix
  if (node.id.includes(':')) {
    return node.id.split(':').slice(1).join(':');
  }
  return node.id;
}

export function GraphVisualization({ 
  maxNodes = 100,
  highlightNodeId = null,
  filterType = null,
  searchQuery = '',
  onNodeSelect,
  onTypeFilter
}: GraphVisualizationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  // Resize observer to track container size
  useEffect(() => {
    if (!containerRef.current) return;
    
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });
    
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  const loadGraphData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/kg/export');
      const data = await response.json();
      
      const allNodes: GraphNode[] = data.nodes || [];
      
      // Smart sampling: ensure representation from all projects
      let limitedNodes: GraphNode[];
      if (allNodes.length <= maxNodes) {
        limitedNodes = allNodes;
      } else {
        // Group by project key (extracted from id like "PROJ-123")
        const byProject = new Map<string, GraphNode[]>();
        const nonIssues: GraphNode[] = [];
        
        for (const node of allNodes) {
          const match = node.id.match(/^([A-Z]+)-\d+$/);
          if (match) {
            const proj = match[1];
            if (!byProject.has(proj)) byProject.set(proj, []);
            byProject.get(proj)!.push(node);
          } else {
            nonIssues.push(node);
          }
        }
        
        // Allocate nodes proportionally per project, ensuring each project gets some
        const projectKeys = Array.from(byProject.keys());
        const nodesPerProject = Math.max(5, Math.floor((maxNodes - nonIssues.length) / Math.max(1, projectKeys.length)));
        
        limitedNodes = [];
        for (const proj of projectKeys) {
          const projNodes = byProject.get(proj)!;
          // Shuffle and take sample
          const shuffled = projNodes.sort(() => Math.random() - 0.5);
          limitedNodes.push(...shuffled.slice(0, nodesPerProject));
        }
        
        // Add non-issue nodes (projects, users, etc)
        limitedNodes.push(...nonIssues.slice(0, 50));
        
        // If still under limit, add more randomly
        if (limitedNodes.length < maxNodes) {
          const usedIds = new Set(limitedNodes.map(n => n.id));
          const remaining = allNodes.filter(n => !usedIds.has(n.id));
          limitedNodes.push(...remaining.slice(0, maxNodes - limitedNodes.length));
        }
        
        // Trim to maxNodes
        limitedNodes = limitedNodes.slice(0, maxNodes);
      }
      
      const nodeIds = new Set(limitedNodes.map((n: GraphNode) => n.id));
      const limitedEdges = (data.edges || []).filter(
        (e: GraphEdge) => nodeIds.has(e.source) && nodeIds.has(e.target)
      );
      
      console.log(`Graph loaded: ${limitedNodes.length} nodes from ${new Set(limitedNodes.map(n => n.id.split('-')[0])).size} projects`);
      
      setGraphData({
        nodes: limitedNodes,
        edges: limitedEdges
      });
      setError(null);
    } catch (err) {
      console.error('Failed to load graph:', err);
      setError('Failed to load graph data');
    } finally {
      setLoading(false);
    }
  }, [maxNodes]);

  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  useEffect(() => {
    if (!graphData || !svgRef.current || graphData.nodes.length === 0) return;
    if (dimensions.width <= 0 || dimensions.height <= 0) return;

    const { width, height } = dimensions;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Add zoom behavior
    const g = svg.append('g');
    
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    
    svg.call(zoom);

    // Create force simulation
    const simulation = d3.forceSimulation(graphData.nodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(80)
      )
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(25));

    // Create edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(graphData.edges)
      .enter()
      .append('line')
      .attr('stroke', '#b3bac5')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6);

    // Create nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(graphData.nodes)
      .enter()
      .append('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Node circles - use inferred type for better coloring
    node.append('circle')
      .attr('r', 12)
      .attr('fill', (d) => {
        const inferredType = inferNodeType(d);
        return typeColors[inferredType] || typeColors.unknown;
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .on('click', (_, d) => setSelectedNode(d))
      .on('mouseover', function() {
        d3.select(this).attr('r', 16);
      })
      .on('mouseout', function() {
        d3.select(this).attr('r', 12);
      });

    // Node labels - show cleaner display name
    node.append('text')
      .text((d) => {
        const displayName = getDisplayName(d);
        return displayName.length > 12 ? displayName.substring(0, 12) + '...' : displayName;
      })
      .attr('x', 15)
      .attr('y', 4)
      .attr('font-size', '10px')
      .attr('fill', '#42526e');

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [graphData, dimensions]);

  // Effect to handle highlighting and filtering
  useEffect(() => {
    if (!svgRef.current || !graphData) return;
    
    const svg = d3.select(svgRef.current);
    const searchLower = searchQuery.toLowerCase();
    
    // Update node visibility and highlighting
    svg.selectAll('.nodes g').each(function(d: any) {
      const nodeGroup = d3.select(this);
      const circle = nodeGroup.select('circle');
      const text = nodeGroup.select('text');
      
      // Determine if this node matches filters
      const matchesType = !filterType || d.type === filterType;
      const matchesSearch = !searchQuery || 
        d.id.toLowerCase().includes(searchLower) ||
        (d.title && d.title.toLowerCase().includes(searchLower));
      const isHighlighted = highlightNodeId === d.id;
      const isSelected = selectedNode?.id === d.id;
      
      // Calculate opacity
      const hasActiveFilter = filterType || searchQuery;
      const isMatch = matchesType && matchesSearch;
      const opacity = hasActiveFilter ? (isMatch ? 1 : 0.15) : 1;
      
      // Apply styles
      nodeGroup.attr('opacity', opacity);
      
      // Highlight effect
      if (isHighlighted || isSelected) {
        circle
          .attr('r', 18)
          .attr('stroke', '#0052cc')
          .attr('stroke-width', 4);
        text
          .attr('font-weight', 'bold')
          .attr('font-size', '12px');
      } else {
        circle
          .attr('r', 12)
          .attr('stroke', '#fff')
          .attr('stroke-width', 2);
        text
          .attr('font-weight', 'normal')
          .attr('font-size', '10px');
      }
    });
    
    // Update edge opacity based on connected nodes
    svg.selectAll('.links line').each(function(d: any) {
      const line = d3.select(this);
      const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
      const targetId = typeof d.target === 'object' ? d.target.id : d.target;
      
      const hasActiveFilter = filterType || searchQuery;
      if (!hasActiveFilter) {
        line.attr('stroke-opacity', 0.6);
        return;
      }
      
      // Check if either endpoint matches
      const sourceMatches = graphData.nodes.some(n => {
        if (n.id !== sourceId) return false;
        const matchesType = !filterType || n.type === filterType;
        const matchesSearch = !searchQuery || 
          n.id.toLowerCase().includes(searchLower) ||
          (n.title && n.title.toLowerCase().includes(searchLower));
        return matchesType && matchesSearch;
      });
      
      const targetMatches = graphData.nodes.some(n => {
        if (n.id !== targetId) return false;
        const matchesType = !filterType || n.type === filterType;
        const matchesSearch = !searchQuery || 
          n.id.toLowerCase().includes(searchLower) ||
          (n.title && n.title.toLowerCase().includes(searchLower));
        return matchesType && matchesSearch;
      });
      
      line.attr('stroke-opacity', (sourceMatches && targetMatches) ? 0.6 : 0.08);
    });
  }, [graphData, highlightNodeId, filterType, searchQuery, selectedNode]);

  // Notify parent of node selection
  useEffect(() => {
    if (onNodeSelect) {
      onNodeSelect(selectedNode);
    }
  }, [selectedNode, onNodeSelect]);

  const containerStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const messageStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    height: '100%',
    color: '#5e6c84',
    fontSize: '0.95rem',
  };

  if (loading) {
    return (
      <div ref={containerRef} style={containerStyle}>
        <div style={messageStyle}>Loading graph visualization...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div ref={containerRef} style={containerStyle}>
        <div style={{ ...messageStyle, color: '#de350b' }}>{error}</div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div ref={containerRef} style={containerStyle}>
        <div style={messageStyle}>No graph data available. Try populating the knowledge graph first.</div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={containerStyle}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      
      {/* Legend - Clickable to filter */}
      <div style={{ 
        position: 'absolute', 
        top: 12, 
        left: 12, 
        background: 'rgba(255,255,255,0.95)', 
        padding: '10px 14px', 
        borderRadius: '6px',
        fontSize: '11px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        border: '1px solid #dfe1e6'
      }}>
        <div style={{ 
          fontWeight: 600, 
          marginBottom: '6px', 
          color: '#172b4d',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>Node Types</span>
          {filterType && onTypeFilter && (
            <button 
              onClick={() => onTypeFilter(null)}
              style={{
                background: '#de350b',
                color: 'white',
                border: 'none',
                borderRadius: '3px',
                fontSize: '9px',
                padding: '2px 6px',
                cursor: 'pointer'
              }}
            >
              Clear
            </button>
          )}
        </div>
        {/* Dynamic legend based on actual types in the graph */}
        {(() => {
          // Get unique types from actual graph data, with counts
          const typeCounts: Record<string, number> = {};
          if (graphData?.nodes) {
            for (const node of graphData.nodes) {
              const t = inferNodeType(node);
              typeCounts[t] = (typeCounts[t] || 0) + 1;
            }
          }
          // Sort by count (most common first)
          const sortedTypes = Object.entries(typeCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12); // Limit to 12 types in legend
          
          return sortedTypes.map(([type, count]) => {
            const color = getTypeColor(type);
            const isActive = filterType === type;
            return (
              <div 
                key={type} 
                onClick={() => onTypeFilter && onTypeFilter(isActive ? null : type)}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px', 
                  marginBottom: '3px',
                  padding: '3px 6px',
                  marginLeft: '-6px',
                  marginRight: '-6px',
                  borderRadius: '4px',
                  cursor: onTypeFilter ? 'pointer' : 'default',
                  background: isActive ? '#deebff' : 'transparent',
                  border: isActive ? '1px solid #0052cc' : '1px solid transparent',
                  transition: 'all 0.15s'
                }}
                onMouseOver={(e) => {
                  if (!isActive) e.currentTarget.style.background = '#f4f5f7';
                }}
                onMouseOut={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                <span style={{ 
                  width: 10, 
                  height: 10, 
                  borderRadius: '50%', 
                  background: color, 
                  display: 'inline-block', 
                  flexShrink: 0,
                  boxShadow: isActive ? '0 0 0 2px white, 0 0 0 4px ' + color : 'none'
                }} />
                <span style={{ 
                  color: isActive ? '#0052cc' : '#42526e',
                  fontWeight: isActive ? 600 : 400,
                  flex: 1
                }}>
                  {type.replace(/_/g, ' ')}
                </span>
                <span style={{
                  fontSize: '10px',
                  color: '#6b778c',
                  background: '#f4f5f7',
                  padding: '1px 5px',
                  borderRadius: '10px'
                }}>
                  {count}
                </span>
              </div>
            );
          });
        })()}
      </div>

      {/* Node Info Panel - Type-Specific */}
      {selectedNode && (() => {
        const inferredType = inferNodeType(selectedNode);
        const displayName = getDisplayName(selectedNode);
        const typeColor = typeColors[inferredType] || typeColors.unknown;
        const props = selectedNode.properties || {};
        
        // Count connections for this node
        const connectionCount = graphData?.edges.filter(e => {
          const sourceId = typeof e.source === 'object' ? (e.source as any).id : e.source;
          const targetId = typeof e.target === 'object' ? (e.target as any).id : e.target;
          return sourceId === selectedNode.id || targetId === selectedNode.id;
        }).length || 0;
        
        // Get connected nodes for relationships
        const connections = graphData?.edges.filter(e => {
          const sourceId = typeof e.source === 'object' ? (e.source as any).id : e.source;
          const targetId = typeof e.target === 'object' ? (e.target as any).id : e.target;
          return sourceId === selectedNode.id || targetId === selectedNode.id;
        }).slice(0, 5) || [];

        // Helper to render a property row
        const PropRow = ({ label, value, icon }: { label: string; value: string | undefined | null; icon?: string }) => {
          if (!value) return null;
          return (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '8px' }}>
              {icon && <span style={{ fontSize: '12px', width: '16px' }}>{icon}</span>}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '10px', color: '#6b778c', textTransform: 'uppercase', marginBottom: '2px' }}>{label}</div>
                <div style={{ fontSize: '12px', color: '#172b4d', wordBreak: 'break-word' }}>{value}</div>
              </div>
            </div>
          );
        };

        // Status badge with colors
        const StatusBadge = ({ status }: { status: string | undefined }) => {
          if (!status) return null;
          const statusLower = status.toLowerCase();
          let bg = '#dfe1e6', color = '#42526e';
          if (statusLower.includes('done') || statusLower.includes('closed') || statusLower.includes('resolved')) {
            bg = '#e3fcef'; color = '#006644';
          } else if (statusLower.includes('progress') || statusLower.includes('review')) {
            bg = '#deebff'; color = '#0052cc';
          } else if (statusLower.includes('blocked') || statusLower.includes('cancelled')) {
            bg = '#ffebe6'; color = '#de350b';
          }
          return (
            <span style={{ 
              background: bg, color, 
              padding: '3px 8px', 
              borderRadius: '4px', 
              fontSize: '11px', 
              fontWeight: 600 
            }}>
              {status}
            </span>
          );
        };

        // Priority with color
        const PriorityBadge = ({ priority }: { priority: string | undefined }) => {
          if (!priority) return null;
          const pLower = priority.toLowerCase();
          let color = '#42526e';
          if (pLower.includes('high') || pLower.includes('critical') || pLower.includes('blocker')) color = '#de350b';
          else if (pLower.includes('medium')) color = '#ff991f';
          else if (pLower.includes('low')) color = '#00875a';
          return <span style={{ color, fontWeight: 600 }}>{priority}</span>;
        };

        // Render type-specific content
        const renderTypeContent = () => {
          // Jira issues: story, bug, task, subtask, epic, idea, feature, improvement
          if (['story', 'bug', 'task', 'subtask', 'epic', 'idea', 'feature', 'improvement', 'initiative', 'jira_issue'].includes(inferredType)) {
            return (
              <>
                {/* Status & Priority row */}
                <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  <StatusBadge status={props.status as string} />
                  {props.priority && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span style={{ fontSize: '10px', color: '#6b778c' }}>Priority:</span>
                      <PriorityBadge priority={props.priority as string} />
                    </div>
                  )}
                </div>

                {/* Assignee & Reporter */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                  <PropRow label="Assignee" value={props.assignee as string} icon="👤" />
                  <PropRow label="Reporter" value={props.reporter as string} icon="📝" />
                </div>

                {/* Epic/Parent link */}
                {props.epic_key && <PropRow label="Epic" value={props.epic_key as string} icon="🎯" />}
                {props.parent && !props.epic_key && <PropRow label="Parent" value={props.parent as string} icon="⬆️" />}
                
                {/* Project */}
                {props.project_key && <PropRow label="Project" value={props.project_key as string} icon="📁" />}

                {/* Labels */}
                {props.labels && (props.labels as string[]).length > 0 && (
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ fontSize: '10px', color: '#6b778c', textTransform: 'uppercase', marginBottom: '4px' }}>🏷️ Labels</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {(props.labels as string[]).slice(0, 5).map((label, i) => (
                        <span key={i} style={{ 
                          background: '#f4f5f7', 
                          padding: '2px 6px', 
                          borderRadius: '3px', 
                          fontSize: '10px',
                          color: '#42526e'
                        }}>{label}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Dates */}
                <div style={{ fontSize: '10px', color: '#8993a4', marginTop: '8px' }}>
                  {props.updated && `Updated: ${new Date(props.updated as string).toLocaleDateString()}`}
                </div>
              </>
            );
          }

          // Confluence page
          if (inferredType === 'confluence_page') {
            return (
              <>
                <PropRow label="Space" value={props.space_key as string} icon="📚" />
                <PropRow label="Author" value={props.author as string} icon="✍️" />
                {props.last_modified && (
                  <PropRow label="Last Modified" value={new Date(props.last_modified as string).toLocaleDateString()} icon="🕐" />
                )}
              </>
            );
          }

          // Confluence space
          if (inferredType === 'confluence_space') {
            return (
              <>
                <PropRow label="Space Key" value={props.key as string || selectedNode.id.replace('space:', '')} icon="📚" />
                <PropRow label="Name" value={props.name as string} icon="📄" />
              </>
            );
          }

          // User
          if (inferredType === 'user') {
            return (
              <>
                <PropRow label="Display Name" value={props.displayName as string || displayName} icon="👤" />
                <PropRow label="Email" value={props.email as string} icon="✉️" />
              </>
            );
          }

          // Project
          if (inferredType === 'project') {
            return (
              <>
                <PropRow label="Project Key" value={props.key as string || selectedNode.id.replace('project:', '')} icon="📁" />
                <PropRow label="Name" value={props.name as string} icon="📋" />
              </>
            );
          }

          // Default: show all properties
          return (
            <>
              {Object.entries(props).slice(0, 6).map(([key, value]) => {
                if (value === null || value === undefined || value === '') return null;
                const displayVal = typeof value === 'object' ? JSON.stringify(value) : String(value);
                return <PropRow key={key} label={key.replace(/_/g, ' ')} value={displayVal.slice(0, 100)} />;
              })}
            </>
          );
        };
        
        return (
          <div style={{ 
            position: 'absolute', 
            top: 12, 
            right: 12, 
            background: 'white', 
            padding: '0',
            borderRadius: '10px',
            width: '300px',
            maxHeight: '80vh',
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            border: '1px solid #dfe1e6',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Header with color accent */}
            <div style={{ 
              background: typeColor, 
              padding: '12px 14px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              flexShrink: 0
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ 
                  color: 'white', 
                  fontWeight: 700, 
                  fontSize: '14px',
                  wordBreak: 'break-word',
                  lineHeight: 1.3
                }}>
                  {displayName}
                </div>
                <div style={{ 
                  color: 'rgba(255,255,255,0.85)', 
                  fontSize: '11px',
                  marginTop: '4px',
                  textTransform: 'capitalize'
                }}>
                  {props.issue_type || inferredType.replace(/_/g, ' ')}
                </div>
              </div>
              <button 
                onClick={() => setSelectedNode(null)}
                style={{ 
                  background: 'rgba(255,255,255,0.2)', 
                  border: 'none', 
                  cursor: 'pointer', 
                  fontSize: '16px',
                  width: '28px',
                  height: '28px',
                  borderRadius: '6px',
                  lineHeight: 1,
                  flexShrink: 0,
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'background 0.15s'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.35)'}
                onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
              >
                ✕
              </button>
            </div>
            
            {/* Scrollable Body */}
            <div style={{ padding: '14px', overflowY: 'auto', flex: 1 }}>
              {/* Title/Summary if available */}
              {selectedNode.title && selectedNode.title !== selectedNode.id && selectedNode.title !== displayName && (
                <div style={{ 
                  marginBottom: '12px', 
                  fontSize: '13px', 
                  color: '#172b4d',
                  lineHeight: 1.4,
                  fontWeight: 500
                }}>
                  {selectedNode.title}
                </div>
              )}
              
              {/* Connection count */}
              <div style={{ 
                display: 'flex', 
                gap: '8px',
                marginBottom: '12px'
              }}>
                <div style={{ 
                  background: '#f4f5f7', 
                  borderRadius: '6px', 
                  padding: '6px 10px',
                  textAlign: 'center'
                }}>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: typeColor }}>{connectionCount}</span>
                  <span style={{ fontSize: '10px', color: '#5e6c84', marginLeft: '4px' }}>connections</span>
                </div>
              </div>
              
              {/* Type-specific content */}
              {renderTypeContent()}

              {/* Connected entities (first 5) */}
              {connections.length > 0 && (
                <div style={{ marginTop: '12px', borderTop: '1px solid #f0f0f0', paddingTop: '12px' }}>
                  <div style={{ fontSize: '10px', color: '#6b778c', textTransform: 'uppercase', marginBottom: '6px' }}>
                    🔗 Connected To
                  </div>
                  {connections.map((edge, i) => {
                    const sourceId = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
                    const targetId = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
                    const otherId = sourceId === selectedNode.id ? targetId : sourceId;
                    const rel = edge.relationship;
                    return (
                      <div key={i} style={{ 
                        fontSize: '11px', 
                        color: '#42526e', 
                        padding: '4px 0',
                        borderBottom: i < connections.length - 1 ? '1px solid #f8f9fa' : 'none'
                      }}>
                        <span style={{ color: '#8993a4' }}>{rel}:</span> {otherId}
                      </div>
                    );
                  })}
                  {connectionCount > 5 && (
                    <div style={{ fontSize: '10px', color: '#8993a4', marginTop: '4px' }}>
                      +{connectionCount - 5} more...
                    </div>
                  )}
                </div>
              )}

              {/* Full ID if different from display */}
              {selectedNode.id !== displayName && (
                <div style={{ 
                  fontSize: '10px', 
                  color: '#8993a4',
                  padding: '6px 8px',
                  background: '#f8f9fa',
                  borderRadius: '4px',
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                  marginTop: '12px'
                }}>
                  ID: {selectedNode.id}
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* Stats */}
      <div style={{ 
        position: 'absolute', 
        bottom: 12, 
        left: 12, 
        background: 'rgba(255,255,255,0.95)', 
        padding: '8px 12px', 
        borderRadius: '4px',
        fontSize: '11px',
        color: '#5e6c84',
        border: '1px solid #dfe1e6'
      }}>
        Showing {graphData.nodes.length} nodes, {graphData.edges.length} edges
        {graphData.nodes.length >= maxNodes && <span> (limited)</span>}
      </div>

      {/* Zoom hint */}
      <div style={{ 
        position: 'absolute', 
        bottom: 12, 
        right: 12, 
        background: 'rgba(255,255,255,0.9)', 
        padding: '6px 10px', 
        borderRadius: '4px',
        fontSize: '10px',
        color: '#8993a4',
        border: '1px solid #dfe1e6'
      }}>
        Scroll to zoom • Drag to pan
      </div>
    </div>
  );
}
