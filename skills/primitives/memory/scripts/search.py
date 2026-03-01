#!/usr/bin/env python3
"""Memory search - search memory from SQLite with FTS5 when query present."""
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from constants import DB_FILENAME


def _ts_to_date(ts) -> str | None:
    """Format Unix timestamp to YYYY-MM-DD HH:MM:SS."""
    if ts is None:
        return None
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(ts))))
    except (TypeError, ValueError, OSError):
        return None


def _fts5_query(query_str: str) -> str:
    """Build FTS5 MATCH expression: AND of non-empty tokens, escape double-quotes."""
    if not query_str:
        return ""
    tokens = [t.strip() for t in re.split(r"\s+", query_str) if t.strip()]
    if not tokens:
        return ""
    escaped = [t.replace('"', '') for t in tokens if t]
    return " AND ".join(f'"{t}"' for t in escaped)


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = _resolve_db_path(params)
    query_str = (args.get("query") or params.get("query", "")).strip()
    limit = int(args.get("top_k") or args.get("limit") or params.get("limit") or 5)
    date_range = args.get("date_range") or params.get("date_range")
    session_id = args.get("session_id") or params.get("_executor_session_id")
    # Normalize: accept [start, end] array (from time.calculate flow)
    if isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
        date_range = {"start": str(date_range[0])[:10], "end": str(date_range[1])[:10]}
    if not db_path.exists():
        print(json.dumps({"results": []}))
        return

    use_fts = bool(query_str)
    fts_expr = _fts5_query(query_str) if use_fts else ""

    def _base_filter(tbl: str = "") -> tuple[str, list]:
        sql_extra = ""
        pargs: list = []
        col = f"{tbl}created_at" if tbl else "created_at"
        if date_range and isinstance(date_range, dict):
            start = (date_range.get("start") or "")[:10]
            end = (date_range.get("end") or "")[:10]
            if start:
                try:
                    pargs.append(time.mktime(time.strptime(start, "%Y-%m-%d")))
                    sql_extra += f" AND {col} >= ?"
                except ValueError:
                    pass
            if end:
                try:
                    pargs.append(time.mktime(time.strptime(end, "%Y-%m-%d")) + 86400)
                    sql_extra += f" AND {col} < ?"
                except ValueError:
                    pass
        return sql_extra, pargs

    def _run_query(sess_filter: str | None, sess_arg: str | None, lim: int) -> list[dict]:
        tbl = "m." if (use_fts and fts_expr) else ""
        base_extra, base_args = _base_filter(tbl)
        if use_fts and fts_expr:
            sql = (
                "SELECT m.id, m.session_id, m.role, m.content, m.created_at "
                "FROM memory_long_term m "
                "JOIN memory_fts ON memory_fts.rowid = m.id AND memory_fts MATCH ? "
                f"WHERE 1=1 {base_extra}"
            )
            pargs = [fts_expr] + base_args
        else:
            like_val = f"%{query_str}%" if query_str else "%%"
            sql = f"SELECT id, session_id, role, content, created_at FROM memory_long_term WHERE content LIKE ? {base_extra}"
            pargs = [like_val] + base_args
        if sess_filter:
            sql += f" AND {tbl}session_id = ?"
            pargs.append(sess_arg)
        sql += f" ORDER BY {tbl}created_at DESC LIMIT ?"
        pargs.append(lim)
        cur = conn.execute(sql, pargs)
        return [
            {"id": r[0], "session_id": r[1], "role": r[2], "content": (r[3] or ""), "created_at": r[4], "date": _ts_to_date(r[4])}
            for r in cur.fetchall()
        ]

    conn = sqlite3.connect(str(db_path))
    try:
        rows: list[dict] = []
        seen_ids: set[int] = set()
        if session_id:
            short_term = _run_query("session_id = ?", session_id, limit)
            for r in short_term:
                seen_ids.add(r["id"])
                rows.append(r)
        if len(rows) < limit:
            long_limit = limit - len(rows)
            long_tbl = "m." if (use_fts and fts_expr) else ""
            long_base, long_args = _base_filter(long_tbl)
            if use_fts and fts_expr:
                sql = (
                    "SELECT m.id, m.session_id, m.role, m.content, m.created_at "
                    "FROM memory_long_term m "
                    "JOIN memory_fts ON memory_fts.rowid = m.id AND memory_fts MATCH ? "
                    f"WHERE 1=1 {long_base}"
                )
                pargs = [fts_expr] + long_args
            else:
                like_val = f"%{query_str}%" if query_str else "%%"
                sql = f"SELECT id, session_id, role, content, created_at FROM memory_long_term WHERE content LIKE ? {long_base}"
                pargs = [like_val] + long_args
            if seen_ids:
                placeholders = ",".join("?" * len(seen_ids))
                sql += f" AND {long_tbl}id NOT IN ({placeholders})"
                pargs.extend(list(seen_ids))
            sql += f" ORDER BY {long_tbl}created_at DESC LIMIT ?"
            pargs.append(long_limit)
            cur = conn.execute(sql, pargs)
            for r in cur.fetchall():
                row = {"id": r[0], "session_id": r[1], "role": r[2], "content": (r[3] or ""), "created_at": r[4], "date": _ts_to_date(r[4])}
                if row["id"] not in seen_ids:
                    rows.append(row)
                    seen_ids.add(row["id"])
    finally:
        conn.close()
    rows = sorted(rows, key=lambda x: x["created_at"] or 0, reverse=True)[:limit]
    print(json.dumps({"results": rows}))


if __name__ == "__main__":
    main()
