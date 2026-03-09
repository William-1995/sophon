#!/usr/bin/env python3
"""
excel-ops/execute action - Fetch (crawl/search) + LLM extract + write.

Same logic as enrich. Uses crawler and search skills internally (not exposed to LLM).
"""
import runpy
from pathlib import Path

# Reuse enrich implementation - run as __main__ so it reads stdin and prints JSON
_enrich_path = Path(__file__).resolve().parent / "enrich.py"
runpy.run_path(str(_enrich_path), run_name="__main__")
