"""
Knowledge Graph Manager - Convenience wrapper.

This is a root-level convenience script that calls the maintenance module.

Usage:
  python fix_kg.py             # Full repopulate + all fixes
  python fix_kg.py --fix-only  # Only fix orphans + sync
  python fix_kg.py --stats     # Just show stats
"""
import sys
import subprocess

# Forward all arguments to the maintenance module
args = ['python', '-m', 'app.maintenance.kg_manager'] + sys.argv[1:]
subprocess.run(args)

