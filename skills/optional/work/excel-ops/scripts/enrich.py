#!/usr/bin/env python3
"""
excel-ops/enrich action.

Reads Excel sheet(s), uses id_column (and optional company_column) for search per row.
Uses search skill only (no crawl). Batches rows: N searches in parallel -> 1 LLM call -> write.
Copies copy_columns from source to target when cross-sheet. Writes to *_FILLED.xlsx by default.
"""
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

_project_root = Path(
    os.environ.get("SOPHON_ROOT", Path(__file__).resolve().parent.parent.parent.parent.parent)
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.executor import execute_skill  # type: ignore
from providers import get_provider  # type: ignore

from _config import (
    CONTENT_PREVIEW_LEN,
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
    MODE_OVERWRITE,
    SEARCH_NUM_RESULTS,
    START_ROW_DATA_DEFAULT,
)
from _context import ResolvedContext, resolve_context, resolve_path
from _excel import (
    build_column_index,
    extract_headers,
    ensure_columns_exist,
    load_sheet,
)
from _file_io import determine_output_path

logger = logging.getLogger(__name__)


def _parse_args(params: dict) -> dict[str, Any]:
    """Parse and normalize arguments from params."""
    args = params.get("arguments") or params
    sheet_name = args.get("sheet_name")
    source_sheet = args.get("source_sheet") or sheet_name
    batch_size = int(args.get("batch_size", DEFAULT_BATCH_SIZE))
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    return {
        "path_raw": str(args.get("path", "")).strip(),
        "source_sheet": source_sheet,
        "target_sheet": args.get("target_sheet") or source_sheet,
        "id_column": str(args.get("id_column", "")).strip(),
        "company_column": args.get("company_column"),
        "target_columns": args.get("target_columns") or [],
        "copy_columns": args.get("copy_columns") or [],
        "start_row": int(args.get("start_row", START_ROW_DATA_DEFAULT)),
        "max_rows": args.get("max_rows"),
        "batch_size": batch_size,
        "mode": str(args.get("mode", "copy")).strip().lower() or "copy",
        "instructions": str(args.get("instructions", "")).strip(),
    }


def _validate_args(args: dict[str, Any]) -> dict[str, Any] | None:
    """Validate required arguments. Returns error dict or None."""
    if not args.get("path_raw"):
        return {"error": "path is required"}
    if not args.get("id_column"):
        return {"error": "id_column is required"}
    target_columns = args.get("target_columns") or []
    if not isinstance(target_columns, list) or not target_columns:
        return {"error": "target_columns must be a non-empty array of column names"}
    return None


def _load_workbook_and_sheets(
    full_path: Path,
    source_sheet: str,
    target_sheet: str,
) -> tuple[Any, Any, Any] | dict[str, Any]:
    """Load workbook and resolve source/target worksheets. Returns (wb, ws_source, ws_target) or error."""
    sheet_tuple, err = load_sheet(full_path, source_sheet)
    if err:
        return err
    wb, ws_source = sheet_tuple  # type: ignore[misc]
    if source_sheet != target_sheet:
        if target_sheet not in wb.sheetnames:
            return {"error": f"target_sheet '{target_sheet}' not found. Available: {wb.sheetnames}"}
        ws_target = wb[target_sheet]
    else:
        ws_target = ws_source
    return (wb, ws_source, ws_target)


def _prepare_columns(
    ws_source,
    ws_target,
    args: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int]] | dict[str, Any]:
    """Build column indices, validate, ensure target columns. Returns (col_source, col_target) or error."""
    id_column = args["id_column"]
    company_column = args.get("company_column")
    target_columns = args["target_columns"]
    copy_columns = args.get("copy_columns") or []

    headers_source = extract_headers(ws_source)
    if not headers_source:
        return {"error": "Source sheet header row (row 1) is empty"}
    col_source = build_column_index(headers_source)

    if id_column not in col_source:
        return {"error": f"id_column '{id_column}' not found in source headers: {headers_source}"}
    if company_column and company_column not in col_source:
        return {"error": f"company_column '{company_column}' not found in source headers: {headers_source}"}

    headers_target = extract_headers(ws_target)
    if not headers_target:
        return {"error": "Target sheet header row (row 1) is empty"}
    col_target = build_column_index(headers_target)

    all_cols = list(target_columns) + list(copy_columns)
    _, col_target = ensure_columns_exist(ws_target, headers_target, col_target, all_cols)
    return (col_source, col_target)


def _compute_row_range(
    ws_source,
    start_row: int,
    max_rows: Any,
) -> tuple[int, int] | dict[str, Any]:
    """Compute start_row and end_row. Returns (start_row, end_row) or error."""
    max_row = ws_source.max_row
    if max_rows is not None:
        try:
            max_rows_int = int(max_rows)
            end_row = min(start_row + max_rows_int - 1, max_row)
        except (TypeError, ValueError):
            return {"error": f"Invalid max_rows: {max_rows!r}"}
    else:
        end_row = max_row
    if start_row < 2:
        start_row = 2
    if start_row > end_row:
        return {"error": f"Empty range: start_row={start_row}, end_row={end_row}"}
    return (start_row, end_row)


def _extract_json(text: str) -> str:
    """Extract JSON from markdown code fences or raw text."""
    s = str(text).strip()
    if "```" in s:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if m:
            return m.group(1).strip()
        first = s.find("```")
        rest = s[first + 3:]
        if "```" in rest:
            inner = rest.split("```", 1)[0]
            return inner.strip()
    return s


def _build_search_query(row_values: dict[str, Any], id_column: str, company_column: str | None) -> str:
    """Build search query: company + id when company_column set, else id_column value."""
    id_val = str(row_values.get(id_column) or "").strip()
    if not id_val:
        return ""
    if company_column:
        company_val = str(row_values.get(company_column) or "").strip()
        if company_val:
            return f"{company_val} {id_val}"
    return id_val


def _read_row(ws_source, row_idx: int, col_source: dict[str, int]) -> dict[str, Any]:
    """Read row values from worksheet."""
    return {
        name: ws_source.cell(row=row_idx, column=idx).value
        for name, idx in col_source.items()
    }


def _copy_row_to_target(
    ws_source,
    ws_target,
    row_idx: int,
    row_values: dict[str, Any],
    col_source: dict[str, int],
    col_target: dict[str, int],
    copy_columns: list[str],
) -> None:
    """Copy copy_columns from source row to target row."""
    if not copy_columns:
        return
    for col in copy_columns:
        if col not in col_source or col not in col_target:
            continue
        val = row_values.get(col)
        if val is None:
            val = ""
        ws_target.cell(row=row_idx, column=col_target[col], value=val)


async def _search_row(
    ctx: ResolvedContext,
    row_values: dict[str, Any],
    id_column: str,
    company_column: Any,
) -> str:
    """Run search skill for one row. Returns search result text or empty string."""
    query = _build_search_query(row_values, id_column, company_column)
    if not query:
        return ""
    search_result = await execute_skill(
        skill_name="search",
        action="search",
        arguments={"query": query, "num": SEARCH_NUM_RESULTS},
        workspace_root=ctx.workspace_root,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
        root=_project_root,
        db_path=ctx.db_path if ctx.db_path.exists() else None,
        call_stack=ctx.call_stack,
    )
    if search_result.get("error"):
        return ""
    return str(search_result.get("result") or "")


async def _enrich_batch(
    ctx: ResolvedContext,
    ws_source,
    ws_target,
    col_source: dict[str, int],
    col_target: dict[str, int],
    row_indices: list[int],
    id_column: str,
    company_column: Any,
    target_columns: list[str],
    copy_columns: list[str],
    instructions: str,
) -> tuple[int, list[dict[str, Any]]]:
    """Process a batch: read rows, search in parallel, one LLM call, return (updated_count, errors)."""
    rows_data: list[dict[str, Any]] = []
    for row_idx in row_indices:
        row_values = _read_row(ws_source, row_idx, col_source)
        query = _build_search_query(row_values, id_column, company_column)
        if not query:
            continue
        rows_data.append({"row_idx": row_idx, "row_values": row_values, "query": query})

    if not rows_data:
        for row_idx in row_indices:
            _copy_row_to_target(
                ws_source, ws_target, row_idx,
                _read_row(ws_source, row_idx, col_source),
                col_source, col_target, copy_columns,
            )
        return 0, []

    search_results = await asyncio.gather(
        *[_search_row(ctx, r["row_values"], id_column, company_column) for r in rows_data],
        return_exceptions=True,
    )
    for r, content in zip(rows_data, search_results):
        r["search_content"] = str(content) if not isinstance(content, Exception) else ""

    for row_idx in row_indices:
        _copy_row_to_target(
            ws_source, ws_target, row_idx,
            _read_row(ws_source, row_idx, col_source),
            col_source, col_target, copy_columns,
        )

    batch_parts = []
    for r in rows_data:
        batch_parts.append(
            f"Row {r['row_idx']} (id={r['query']}):\n"
            f"  Excel row: {json.dumps(r['row_values'], ensure_ascii=False)}\n"
            f"  Search snippets:\n{r['search_content'][:CONTENT_PREVIEW_LEN]}\n"
        )

    sys_prompt = (
        "You are an assistant that fills Excel columns from web search snippets. "
        "Return ONLY a JSON array of objects. Each object corresponds to one row in order. "
        "Each object must have keys for every target column. Use empty string when uncertain."
    )
    user_instr = instructions or (
        f"Infer values for target columns {target_columns} from the search snippets. "
        "If unsure, use empty string."
    )
    user_prompt = (
        f"Target columns: {target_columns}\n"
        f"Instructions: {user_instr}\n\n"
        "Batch (rows in order):\n"
        + "\n---\n".join(batch_parts)
        + "\n\n"
        "Respond ONLY with a JSON array of objects, one per row, each object mapping target column names to values. "
        "Example: [{\"col1\": \"val1\", \"col2\": \"\"}, ...]"
    )

    provider = get_provider()
    resp = await provider.chat(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = resp.get("content") or ""
    text = _extract_json(content)

    try:
        arr = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return 0, [
            {"row": r["row_idx"], "id_value": r["query"], "reason": f"LLM JSON parse error: {exc!s}"}
            for r in rows_data
        ]

    if not isinstance(arr, list):
        return 0, [{"row": rows_data[0]["row_idx"], "reason": f"LLM output is not an array: {type(arr)!r}"}]

    rows_updated = 0
    errors: list[dict[str, Any]] = []
    for i, r in enumerate(rows_data):
        mapping = arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
        row_idx = r["row_idx"]
        if not mapping:
            errors.append({"row": row_idx, "id_value": r["query"], "reason": "No mapping in LLM response"})
            continue
        row_updated = False
        for col in target_columns:
            if col not in col_target:
                continue
            value = mapping.get(col)
            if value is None:
                value = ""
            ws_target.cell(row=row_idx, column=col_target[col], value=value)
            row_updated = True
        if row_updated:
            rows_updated += 1
            logger.info("[excel-ops.enrich] row=%d batch_updated", row_idx)
    return rows_updated, errors


def _save_workbook_and_format_output(
    wb: Any,
    full_path: Path,
    mode: str,
    workspace_root: Path,
) -> str:
    """Save workbook and return output path string relative to workspace if possible."""
    out_path = determine_output_path(full_path, mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    output_str = str(out_path)
    if output_str.startswith(str(workspace_root)):
        output_str = str(out_path.relative_to(workspace_root))
    return output_str


async def _enrich_async(params: dict) -> dict[str, Any]:
    args = _parse_args(params)
    if err := _validate_args(args):
        return err

    ctx = resolve_context(params)
    full_path = resolve_path(params, args["path_raw"])

    load_result = _load_workbook_and_sheets(full_path, args["source_sheet"], args["target_sheet"])
    if isinstance(load_result, dict):
        return load_result
    wb, ws_source, ws_target = load_result

    col_result = _prepare_columns(ws_source, ws_target, args)
    if isinstance(col_result, dict):
        return col_result
    col_source, col_target = col_result

    range_result = _compute_row_range(ws_source, args["start_row"], args["max_rows"])
    if isinstance(range_result, dict):
        return range_result
    start_row, end_row = range_result

    id_column = args["id_column"]
    company_column = args.get("company_column")
    target_columns = args["target_columns"]
    copy_columns = args["copy_columns"]
    batch_size = args["batch_size"]
    instructions = args["instructions"]
    mode = args["mode"]

    processed_rows = 0
    updated_rows = 0
    errors: list[dict[str, Any]] = []

    current = start_row
    while current <= end_row:
        batch_end = min(current + batch_size - 1, end_row)
        row_indices = list(range(current, batch_end + 1))
        batch_updated, batch_errors = await _enrich_batch(
            ctx,
            ws_source,
            ws_target,
            col_source,
            col_target,
            row_indices,
            id_column,
            company_column,
            target_columns,
            copy_columns,
            instructions,
        )
        processed_rows += len(row_indices)
        updated_rows += batch_updated
        errors.extend(batch_errors)
        current = batch_end + 1

    output_path_str = _save_workbook_and_format_output(wb, full_path, mode, ctx.workspace_root)

    result: dict[str, Any] = {
        "output_path": output_path_str,
        "processed_rows": processed_rows,
        "updated_rows": updated_rows,
        "target_columns": target_columns,
    }
    if copy_columns:
        result["copy_columns"] = copy_columns
    if errors:
        result["errors"] = errors
    logger.info(
        "[excel-ops.enrich] done processed=%d errors=%d output=%s",
        processed_rows, len(errors), result.get("output_path", ""),
    )
    return result


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_enrich_async(params))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
