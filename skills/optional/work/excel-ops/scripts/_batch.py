"""
Excel-Ops Enrich - Batch processing.

Handles batch processing of rows: parallel search, LLM extraction, and writing.
"""

import asyncio
import json
import logging
from typing import Any

from _config import (
    ENRICH_DEFAULT_INSTRUCTIONS_TEMPLATE,
    ENRICH_LLM_PROMPT_TEMPLATE,
    ENRICH_SYSTEM_PROMPT,
)
from _context import ResolvedContext
from _search import build_search_query, extract_json
from core.executor import execute_skill  # type: ignore

logger = logging.getLogger(__name__)


def read_row(ws, row_idx: int, col_index: dict[str, int]) -> dict[str, Any]:
    """Read row values from worksheet."""
    return {
        name: ws.cell(row=row_idx, column=idx).value
        for name, idx in col_index.items()
    }


def copy_row_columns(
    ws_source,
    ws_target,
    row_idx: int,
    col_index_source: dict[str, int],
    col_index_target: dict[str, int],
    copy_columns: list[str],
) -> None:
    """Copy specified columns from source to target row."""
    if not copy_columns:
        return

    for col in copy_columns:
        if col not in col_index_source or col not in col_index_target:
            continue
        val = ws_source.cell(row=row_idx, column=col_index_source[col]).value
        ws_target.cell(
            row=row_idx,
            column=col_index_target[col],
            value=val if val is not None else "",
        )


async def search_for_row(
    query: str,
    ctx: ResolvedContext,
    search_num: int,
    project_root,
) -> str:
    """Execute search for a single query."""
    if not query:
        return ""

    result = await execute_skill(
        skill_name="search",
        action="search",
        arguments={"query": query, "num": search_num},
        workspace_root=ctx.workspace_root,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
        root=project_root,
        db_path=ctx.db_path if ctx.db_path.exists() else None,
        call_stack=ctx.call_stack,
    )

    if result.get("error"):
        return ""

    return str(result.get("result") or "")


async def process_batch(
    row_indices: list[int],
    ws_source,
    ws_target,
    col_index_source: dict[str, int],
    col_index_target: dict[str, int],
    target_columns: list[str],
    id_column: str,
    company_column: str | None,
    copy_columns: list[str],
    instructions: str,
    provider,
    ctx: ResolvedContext,
    project_root,
    search_num: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Process a batch of rows.

    Returns:
        Tuple of (updated_count, errors).
    """
    # Read rows and build queries
    rows_data: list[dict[str, Any]] = []
    for row_idx in row_indices:
        row_values = read_row(ws_source, row_idx, col_index_source)
        query = build_search_query(row_values, id_column, company_column)
        if not query:
            continue
        rows_data.append(
            {"row_idx": row_idx, "row_values": row_values, "query": query}
        )

    if not rows_data:
        return 0, []

    # Parallel search
    search_results = await asyncio.gather(
        *[
            search_for_row(r["query"], ctx, search_num, project_root)
            for r in rows_data
        ],
        return_exceptions=True,
    )

    for r, content in zip(rows_data, search_results):
        r["search_content"] = (
            str(content) if not isinstance(content, Exception) else ""
        )

    # Copy columns for ALL rows
    for row_idx in row_indices:
        copy_row_columns(
            ws_source,
            ws_target,
            row_idx,
            col_index_source,
            col_index_target,
            copy_columns,
        )

    # Build LLM prompt
    batch_parts = []
    for r in rows_data:
        batch_parts.append(
            f"Row {r['row_idx']} (id={r['query']}):\n"
            f"  Excel row: {json.dumps(r['row_values'], ensure_ascii=False)}\n"
            f"  Search snippets:\n{r['search_content'][:8000]}\n"
        )

    user_instr = instructions or ENRICH_DEFAULT_INSTRUCTIONS_TEMPLATE.format(
        target_columns=target_columns
    )
    user_prompt = ENRICH_LLM_PROMPT_TEMPLATE.format(
        target_columns=target_columns,
        instructions=user_instr,
        batch_data="\n---\n".join(batch_parts),
    )

    # Call LLM
    resp = await provider.chat(
        [
            {"role": "system", "content": ENRICH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

    # Parse response
    content = resp.get("content") or ""
    text = extract_json(content)

    try:
        arr = json.loads(text)
    except Exception as exc:
        return 0, [
            {
                "row": r["row_idx"],
                "id_value": r["query"],
                "reason": f"LLM JSON parse error: {exc}",
            }
            for r in rows_data
        ]

    if not isinstance(arr, list):
        return 0, [
            {
                "row": rows_data[0]["row_idx"],
                "reason": f"LLM output is not an array: {type(arr)}",
            }
        ]

    # Write results
    rows_updated = 0
    errors: list[dict[str, Any]] = []

    for i, r in enumerate(rows_data):
        mapping = (
            arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
        )
        row_idx = r["row_idx"]

        if not mapping:
            errors.append(
                {
                    "row": row_idx,
                    "id_value": r["query"],
                    "reason": "No mapping in LLM response",
                }
            )
            continue

        row_updated = False
        for col in target_columns:
            if col not in col_index_target:
                continue
            value = mapping.get(col, "")
            ws_target.cell(
                row=row_idx,
                column=col_index_target[col],
                value=value if value is not None else "",
            )
            row_updated = True

        if row_updated:
            rows_updated += 1
        logger.info("[excel-ops.enrich] row=%d batch_updated", row_idx)

    return rows_updated, errors
