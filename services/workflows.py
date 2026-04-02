"""Read workflow instance rows from SQLite for admin or status APIs."""

from __future__ import annotations

from typing import Any, Dict, List

from db.schema import get_connection


async def list_workflow_instances() -> List[Dict[str, Any]]:
    """Return workflow instance rows from ``workflow_instances`` (newest first).

    Returns:
        List of dicts with ``instance_id``, ``workflow_id``, ``status``, timestamps,
        and optional ``error_message`` (stringified dates).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                instance_id,
                workflow_id,
                status,
                error_message,
                created_at,
                started_at,
                completed_at
            FROM workflow_instances
            ORDER BY COALESCE(completed_at, started_at, created_at) DESC, instance_id DESC
            """
        )
        items: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            items.append(
                {
                    "instance_id": row["instance_id"],
                    "workflow_id": row["workflow_id"],
                    "status": row["status"],
                    "created_at": str(row["created_at"] or ""),
                    "started_at": str(row["started_at"] or ""),
                    "completed_at": str(row["completed_at"] or ""),
                    "error_message": row["error_message"],
                }
            )
        return items
    finally:
        conn.close()
