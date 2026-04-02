#!/usr/bin/env python3
"""Metrics list - list metric names.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from common.db_utils import resolve_db_path

from db.metrics import list_names


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    db_path = resolve_db_path(params)
    if not db_path.exists():
        print(json.dumps({"names": []}))
        return
    names = list_names(db_path)
    print(json.dumps({"names": names}))


if __name__ == "__main__":
    main()
