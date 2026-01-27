"""
Repopulate Knowledge Graph with ALL Projects
This will load all issues from all projects with proper hierarchical relationships
"""
import sys
sys.path.insert(0, '.')

from app.services.knowledge_graph_service import knowledge_graph_service

print('📊 Current Knowledge Graph Stats:')
print('=' * 60)
stats = knowledge_graph_service.get_graph_stats()
print(f'   Entities: {stats["total_nodes"]}')
print(f'   Relationships: {stats["total_edges"]}')
print(f'   Types: {stats["entity_types"]}')

print('\n🔄 Repopulating with ALL projects and hierarchical relationships...')
print('   • Loading ALL issues from ALL projects (no limits)')
print('   • Creating Project → Issue relationships')
print('   • Creating Epic → Issue relationships')
print('   • Creating Parent → Child relationships')
print('   • Creating User → Issue relationships (assignee, reporter)')
print('   • Creating Label and Component relationships')
print('   This will take 2-5 minutes depending on issue count...\n')

# Clear and repopulate
print('🗑️  Clearing knowledge graph...')
knowledge_graph_service.clear_graph()
print('✅ Cleared! Now loading fresh data...\n')

results = knowledge_graph_service.populate_from_services()

print('\n✅ Done! New Knowledge Graph Stats:')
print('=' * 60)
stats = knowledge_graph_service.get_graph_stats()
print(f'   Entities: {stats["total_nodes"]}')
print(f'   Relationships: {stats["total_edges"]}')
print(f'   Entity Types: {stats["entity_types"]}')
print('\n📦 Data Loaded:')
print(f'   Jira Issues: {results.get("jira_issues", 0)}')
print(f'   Jira Projects: {results.get("projects", 0)}')
print(f'   Confluence Pages: {results.get("confluence_pages", 0)}')
print(f'\n💡 Projects loaded: ACTHUB, LIFEOPS, SE')
print(f'   • ACTHUB: Project')
print(f'   • LIFEOPS: Project')
print(f'   • SE: Product Discovery')

print('\n🌟 Most Central Entities:')
print('=' * 60)
central = knowledge_graph_service.get_central_entities(limit=15)
for entity_id, score in central:
    entity = knowledge_graph_service.get_entity(entity_id)
    if entity:
        entity_type = entity.get('type') or 'unknown'  # Handle None case
        print(f'   {entity_id:30s} ({entity_type:15s}) - Score: {score:.4f}')

print('\n✨ Knowledge graph is now fully populated!')
print('   Try: python kg_cli.py stats')
print('   Or ask in chat: "Show me all projects in the knowledge graph"')
