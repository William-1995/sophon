#!/usr/bin/env python3
"""Metrics list - list metric names."""
import json
import sys
from pathlib import Path

from constants import DB_FILENAME
from db.metrics import list_names


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    db_path = _resolve_db_path(params)
    if not db_path.exists():
        print(json.dumps({"names": []}))
        return
    names = list_names(db_path)
    print(json.dumps({"names": names}))


if __name__ == "__main__":
    main()
