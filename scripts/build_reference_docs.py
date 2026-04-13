#!/usr/bin/env python3
"""
AoE2 Reference Corpus Generator

Fetches data from Fandom wiki + SiegeEngineers/aoe2techtree and generates
markdown reference files in reference/ with embedded DB comparison tables.

Usage:
    python3 scripts/build_reference_docs.py              # skip existing files
    python3 scripts/build_reference_docs.py --force      # regenerate all
    python3 scripts/build_reference_docs.py --civ Muisca # single civ
    python3 scripts/build_reference_docs.py --unit "Temple Guard"
    python3 scripts/build_reference_docs.py --dry-run    # report only
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# --- CONSTANTS ---
TECHTREE_URL = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"
WIKI_API = "https://ageofempires.fandom.com/api.php"
DB_PATH = Path("webapp/aoe2_reference.db")
REF_DIR = Path("reference")
FLOAT_TOL = 0.01
MATCH = "✅"
MISMATCH = "❌"
MISSING_EXT = "⚠️"
NOT_IN_DB = "❌ NOT IN DB"
TODAY = date.today().isoformat()
WIKI_DELAY = 0.5  # seconds between wiki API calls


# --- STUB FUNCTIONS (to be implemented in later tasks) ---

def fetch_techtree() -> dict:
    raise NotImplementedError

def generate_armor_classes(conn, args, stats): pass
def generate_all_civs(techtree, conn, args, stats): pass
def generate_all_units(techtree, conn, args, stats): pass
def generate_single_civ(name, techtree, conn, args, stats): pass
def generate_single_unit(name, techtree, conn, args, stats): pass
def write_readme(args, stats): pass


def main():
    parser = argparse.ArgumentParser(description="Generate AoE2 reference markdown corpus")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files")
    parser.add_argument("--civ", metavar="NAME", help="Generate only this civ (e.g. Muisca)")
    parser.add_argument("--unit", metavar="NAME", help='Generate only this unit (e.g. "Temple Guard")')
    parser.add_argument("--dry-run", action="store_true", help="Report mismatches, write nothing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}. Run from project root.", file=sys.stderr)
        sys.exit(1)

    print("Fetching SiegeEngineers/aoe2techtree data.json...")
    techtree = fetch_techtree()
    print(f"  → {len(techtree.get('units', {}))} units, {len(techtree.get('civs', []))} civs loaded")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    stats = {"written": 0, "skipped": 0, "mismatches": 0}

    # Always generate armor-classes (fast, no network needed)
    generate_armor_classes(conn, args, stats)

    if args.unit:
        generate_single_unit(args.unit, techtree, conn, args, stats)
    elif args.civ:
        generate_single_civ(args.civ, techtree, conn, args, stats)
    else:
        generate_all_civs(techtree, conn, args, stats)
        generate_all_units(techtree, conn, args, stats)
        write_readme(args, stats)

    conn.close()

    print(f"\nDone. Written: {stats['written']}, Skipped: {stats['skipped']}, Mismatches: {stats['mismatches']}")
    if stats['mismatches'] > 0:
        print("  ❌ Some mismatches found — check the generated files.")


if __name__ == "__main__":
    main()
