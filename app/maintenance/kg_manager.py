"""
Knowledge Graph Manager - Complete KG lifecycle management using nano-graphrag.

This script handles the full Knowledge Graph lifecycle:
1. Clear and repopulate from Jira/Confluence using nano-graphrag
2. nano-graphrag automatically handles:
   - Entity extraction
   - Relationship building  
   - Vector embeddings
   - Community detection and summaries
3. Supports both LOCAL (entity-focused) and GLOBAL (community-focused) search

Uses Ollama for both LLM and embeddings (nomic-embed-text).

Usage:
  python -m app.maintenance.kg_manager             # Full repopulate
  python -m app.maintenance.kg_manager --clear     # Clear and repopulate
  python -m app.maintenance.kg_manager --stats     # Just show stats
  python -m app.maintenance.kg_manager --query "your question"  # Test query
"""
import argparse
import sys
import os
from time import time

# Add project root to path when running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def parse_args():
    parser = argparse.ArgumentParser(description='Knowledge Graph Manager (nano-graphrag)')
    parser.add_argument('--clear', action='store_true', 
                        help='Clear existing data before repopulating')
    parser.add_argument('--stats', action='store_true',
                        help='Only show stats, no modifications')
    parser.add_argument('--resume', action='store_true',
                        help='Resume/regenerate community reports from existing graph')
    parser.add_argument('--query', type=str, default=None,
                        help='Test query against the graph')
    parser.add_argument('--mode', choices=['local', 'global'], default='local',
                        help='Query mode: local (entity-focused) or global (community-focused)')
    parser.add_argument('--context-only', action='store_true',
                        help='Return only retrieved context without LLM response')
    return parser.parse_args()


def fetch_jira_data():
    """Fetch all Jira issues from configured projects"""
    from app.services.tools.jira.jira_service import jira_service
    
    print('\n📥 Fetching Jira issues...')
    
    if not jira_service.client:
        print('   ⚠️ Jira client not available')
        return []
    
    # Get all projects directly from Jira client
    projects = []
    try:
        all_projects = jira_service.client.projects()
        projects = [{"key": p.key, "name": p.name} for p in all_projects]
        print(f'   Found {len(projects)} projects')
    except Exception as e:
        print(f'   ⚠️ Error fetching projects: {e}')
        return []
    
    all_issues = []
    
    for proj in projects:
        project_key = proj.get("key", "UNKNOWN")
        try:
            # Fetch ALL issues for this project (Jira Cloud max is 5000 per request)
            issues = jira_service.search_issues(f'project = "{project_key}" ORDER BY updated DESC', max_results=5000)
            print(f'   📁 {project_key}: {len(issues)} issues')
            all_issues.extend(issues)
        except Exception as e:
            print(f'   ⚠️ Error fetching {project_key}: {e}')
    
    print(f'   ✅ Total: {len(all_issues)} Jira issues')
    return all_issues


def fetch_confluence_data():
    """Fetch Confluence pages"""
    from app.services.tools.confluence.confluence_service import confluence_service
    
    print('\n📥 Fetching Confluence pages...')
    
    try:
        # Search for all pages using a wildcard - Confluence CQL requires non-empty query
        # Uses 'limit' parameter, not 'max_results'
        pages = confluence_service.search_content(query="*", limit=200)
        print(f'   ✅ Found {len(pages)} Confluence pages')
        return pages
    except Exception as e:
        print(f'   ⚠️ Error fetching Confluence: {e}')
        return []


def main():
    """Main function using nano-graphrag"""
    args = parse_args()
    
    from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
    
    print('=' * 60)
    print('Knowledge Graph Manager (nano-graphrag)')
    print('=' * 60)
    print(f'   Working Dir: {nano_graphrag_service.working_dir}')
    print(f'   LLM Model: {nano_graphrag_service.llm_model}')
    print(f'   Embedding Model: {nano_graphrag_service.EMBEDDING_MODEL}')
    
    # Show stats
    stats = nano_graphrag_service.get_stats()
    print(f'\n📊 Current Status:')
    print(f'   Enabled: {stats.get("enabled", False)}')
    print(f'   Has Graph: {stats.get("has_graph", False)}')
    if stats.get("has_graph"):
        print(f'   Graph Nodes: {stats.get("graph_nodes", "?")}')
        print(f'   Graph Edges: {stats.get("graph_edges", "?")}')
        print(f'   Has Vector DB: {stats.get("has_vector_db", False)}')
        print(f'   Has Communities: {stats.get("has_communities", False)}')
    
    if args.stats:
        return
    
    # Resume mode - regenerate community reports from existing graph
    if args.resume:
        print('\n🔄 Resuming: Regenerating community reports from existing graph...')
        if not stats.get("has_graph"):
            print('   ⚠️ No existing graph found! Run without --resume first.')
            return
        
        try:
            start = time()
            # Access the RAG to trigger community report regeneration
            rag = nano_graphrag_service.rag
            
            # Check if we have the graph loaded - it's wrapped in NetworkXStorage
            graph_storage = rag.chunk_entity_relation_graph
            if hasattr(graph_storage, '_graph'):
                graph = graph_storage._graph
                node_count = graph.number_of_nodes()
            elif hasattr(graph_storage, 'graph'):
                graph = graph_storage.graph
                node_count = graph.number_of_nodes()
            else:
                # Try to get node count from stats we already have
                node_count = stats.get("graph_nodes", "unknown")
            
            print(f'   Found graph with {node_count} nodes')
            print('   Generating community reports...')
            print('   (This uses the patched JSON parser for robustness)')
            
            import asyncio
            from nano_graphrag._op import generate_community_report
            from dataclasses import asdict
            
            # Run community report generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    generate_community_report(
                        rag.community_reports,
                        rag.chunk_entity_relation_graph,
                        asdict(rag)
                    )
                )
            finally:
                loop.close()
            
            elapsed = time() - start
            print(f'\n✅ Community reports regenerated in {elapsed:.1f}s!')
        except Exception as e:
            print(f'   ⚠️ Error during resume: {e}')
            import traceback
            traceback.print_exc()
        return
    
    # Query mode
    if args.query:
        print(f'\n🔍 Querying: "{args.query}"')
        print(f'   Mode: {args.mode}')
        print('=' * 60)
        
        start = time()
        result = nano_graphrag_service.query(
            args.query,
            mode=args.mode,
            only_context=args.context_only
        )
        elapsed = time() - start
        
        print(f'\n📝 Response ({elapsed:.2f}s):')
        print('-' * 60)
        print(result)
        print('-' * 60)
        return
    
    # Repopulate mode
    if args.clear:
        print('\n🗑️  Clearing existing nano-graphrag data...')
        nano_graphrag_service.clear()
        print('   ✅ Cleared!')
    
    # Fetch data
    jira_issues = fetch_jira_data()
    confluence_pages = fetch_confluence_data()
    
    if not jira_issues and not confluence_pages:
        print('\n⚠️  No data to populate!')
        return
    
    # Populate nano-graphrag
    print('\n🔄 Populating nano-graphrag...')
    print('   This will:')
    print('   • Chunk documents')
    print('   • Extract entities and relationships (using Ollama LLM)')
    print('   • Build knowledge graph')
    print('   • Create vector embeddings (using nomic-embed-text)')
    print('   • Detect communities and generate summaries')
    print('\n   ⏳ This may take 10-30 minutes depending on data size...\n')
    
    start = time()
    results = nano_graphrag_service.populate_from_jira_confluence(
        jira_issues=jira_issues,
        confluence_pages=confluence_pages
    )
    elapsed = time() - start
    
    print(f'\n✅ Population complete in {elapsed:.1f}s!')
    print(f'   Jira issues: {results["jira_issues"]}')
    print(f'   Confluence pages: {results["confluence_pages"]}')
    print(f'   Total documents: {results["total_documents"]}')
    
    # Test query
    print('\n🔎 Testing queries...')
    test_queries = [
        ("What projects exist?", "local"),
        ("What are the main themes?", "global"),
    ]
    
    for query, mode in test_queries:
        print(f'\n   Q: "{query}" (mode={mode})')
        try:
            result = nano_graphrag_service.query(query, mode=mode)
            # Truncate for display
            result_preview = result[:200] + "..." if len(result) > 200 else result
            print(f'   A: {result_preview}')
        except Exception as e:
            print(f'   ⚠️ Error: {e}')
    
    print('\n✨ Knowledge Graph setup complete!')
    print('   Use: python -m app.maintenance.kg_manager --query "your question"')


if __name__ == "__main__":
    main()
