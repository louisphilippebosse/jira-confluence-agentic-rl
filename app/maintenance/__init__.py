"""
Maintenance module for Knowledge Graph management.

Usage:
  python -m app.maintenance.kg_manager             # Full repopulate + all fixes
  python -m app.maintenance.kg_manager --fix-only  # Only fix orphans + sync
  python -m app.maintenance.kg_manager --stats     # Just show stats
  python -m app.maintenance.kg_manager --skip-communities  # Skip LLM community summaries
  
Or use the convenience wrapper:
  python fix_kg.py
  python fix_kg.py --stats
"""
