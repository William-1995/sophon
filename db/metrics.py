"""Metrics operations - insert and query from SQLite metrics table."""
import json
import time
from pathlib import Path
from typing import Any

from db.schema import get_connection


def insert(
    db_path: Path,
    name: str,
    value: float,
    timestamp: float | None = None,
    tags: dict | None = None,
) -> None:
    """Insert metric point."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO metrics (timestamp, name, value, tags) VALUES (?, ?, ?, ?)",
            (timestamp or time.time(), name, value, json.dumps(tags) if tags else None),
        )
        conn.commit()
    finally:
        conn.close()


def query(
    db_path: Path,
    name: str,
    since: float | None = None,
    until: float | None = None,
    aggregation: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Query metrics. Returns list of {timestamp, value} or aggregated."""
    conn = get_connection(db_path)
    try:
        sql = "SELECT timestamp, value FROM metrics WHERE name = ?"
        params: list[Any] = [name]
        if since is not None:
            sql += " AND timestamp >= ?"
            params.append(since)
        if until is not None:
            sql += " AND timestamp <= ?"
            params.append(until)
        sql += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        data = [{"timestamp": r[0], "value": r[1]} for r in rows]
        if aggregation and data:
            vals = [d["value"] for d in data]
            if aggregation == "avg":
                data = [{"timestamp": data[0]["timestamp"], "value": sum(vals) / len(vals)}]
            elif aggregation == "sum":
                data = [{"timestamp": data[0]["timestamp"], "value": sum(vals)}]
            elif aggregation == "max":
                data = [{"timestamp": data[0]["timestamp"], "value": max(vals)}]
            elif aggregation == "min":
                data = [{"timestamp": data[0]["timestamp"], "value": min(vals)}]
        return data
    finally:
        conn.close()


def list_names(db_path: Path) -> list[str]:
    """List metric names."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT DISTINCT name FROM metrics ORDER BY name")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
