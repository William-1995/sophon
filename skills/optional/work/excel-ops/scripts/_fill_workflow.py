"""
Excel-Ops FillByColumn - Main workflow.

Fill column workflow orchestration.
"""

import logging
from pathlib import Path
from typing import Any

from _config import (
    CONTENT_PREVIEW_LEN,
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
    MODE_COPY,
    RETRIEVE_MODE_DEFAULT,
    SEARCH_NUM_RESULTS,
    START_ROW_DATA_DEFAULT,
)
from _context import ResolvedContext
from _events import emit, execute_with_events
from _excel import build_column_index, ensure_columns_exist, extract_headers, load_sheet
from _extract import extract_batch
from _file_io import determine_output_path, resolve_full_path
from _retrieve import retrieve_batch
from _search import build_search_query
from _batch import copy_row_columns, read_row
from providers import get_provider

logger = logging.getLogger(__name__)


def validate_params(args: dict) -> dict | None:
    """Validate input parameters."""
    if not args.get("path"):
        return {"error": "path is required"}
    if not args.get("key_column"):
        return {"error": "key_column is required"}
    target_columns = args.get("target_columns")
    if not isinstance(target_columns, list) or not target_columns:
        return {"error": "target_columns must be a non-empty list"}
    return None


def setup_workbook_and_columns(args: dict, ctx: ResolvedContext):
    """Load workbook and setup column indices."""
    path_raw = str(args.get("path", "")).strip()
    full_path = resolve_full_path(path_raw, ctx)
    source_sheet = args.get("source_sheet") or args.get("sheet_name")
    target_sheet = args.get("target_sheet") or source_sheet

    sheet_tuple, err = load_sheet(full_path, source_sheet)
    if err:
        return None, None, None, None, None, full_path, err

    wb, ws_source = sheet_tuple  # type: ignore[misc]
    if source_sheet != target_sheet:
        if target_sheet not in wb.sheetnames:
            return (
                None, None, None, None, None, full_path,
                {"error": f"target_sheet '{target_sheet}' not found. Available: {wb.sheetnames}"},
            )
        ws_target = wb[target_sheet]
    else:
        ws_target = ws_source

    col_source = build_column_index(extract_headers(ws_source))
    col_target = build_column_index(extract_headers(ws_target))
    return wb, ws_source, ws_target, col_source, col_target, full_path, None


def _parse_fill_args(args: dict) -> dict[str, Any]:
    """Parse and normalize fill workflow arguments."""
    copy_column_map = args.get("copy_column_map") or {}
    if not isinstance(copy_column_map, dict):
        copy_column_map = {}
    batch_size = int(args.get("batch_size", DEFAULT_BATCH_SIZE))
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    return {
        "key_column": str(args.get("key_column") or args.get("id_column", "")).strip(),
        "company_column": args.get("company_column"),
        "target_columns": args.get("target_columns") or [],
        "copy_columns": args.get("copy_columns") or [],
        "copy_column_map": copy_column_map,
        "start_row": int(args.get("start_row", START_ROW_DATA_DEFAULT)),
        "max_rows": args.get("max_rows"),
        "batch_size": batch_size,
        "mode": str(args.get("mode", MODE_COPY)).strip().lower() or MODE_COPY,
        "instructions": str(args.get("instructions", "")).strip(),
        "retrieve_mode": str(args.get("retrieve_mode", RETRIEVE_MODE_DEFAULT)).strip().lower()
        or RETRIEVE_MODE_DEFAULT,
    }


def _validate_fill_columns(
    col_source: dict[str, int],
    col_target: dict[str, int],
    key_column: str,
    company_column: Any,
    copy_column_map: dict[str, str],
) -> dict[str, Any] | None:
    """Validate columns exist. Returns error dict or None."""
    if key_column not in col_source:
        return {"error": f"key_column '{key_column}' not in source headers"}
    if company_column and company_column not in col_source:
        return {"error": f"company_column '{company_column}' not found"}
    for target_col, source_col in copy_column_map.items():
        if source_col not in col_source:
            return {"error": f"copy_column_map target '{target_col}' maps from missing source column '{source_col}'"}
    return None


def _ensure_target_columns(
    ws_target,
    headers_target: list[str],
    col_target: dict[str, int],
    target_columns: list[str],
    copy_columns: list[str],
    copy_column_map: dict[str, str],
) -> dict[str, int]:
    """Ensure all target columns exist. Returns updated col_target."""
    all_cols = list(target_columns) + list(copy_columns) + list(copy_column_map.keys())
    _, col_target = ensure_columns_exist(ws_target, headers_target, col_target, all_cols)
    return col_target


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
    if start_row < START_ROW_DATA_DEFAULT:
        start_row = START_ROW_DATA_DEFAULT
    if start_row > end_row:
        return {"error": f"Empty range: start_row={start_row}, end_row={end_row}"}
    return (start_row, end_row)


def _collect_rows_with_keys(
    ws_source,
    ws_target,
    col_source: dict[str, int],
    col_target: dict[str, int],
    start_row: int,
    end_row: int,
    key_column: str,
    company_column: Any,
    copy_columns: list[str],
    copy_column_map: dict[str, str],
) -> list[tuple[int, str]]:
    """Collect (row_idx, query) for rows with search query. Copy-only rows handled inline."""
    rows_with_keys: list[tuple[int, str]] = []
    for row_idx in range(start_row, end_row + 1):
        row_vals = read_row(ws_source, row_idx, col_source)
        query = build_search_query(row_vals, key_column, company_column)
        if not query:
            copy_row_columns(ws_source, ws_target, row_idx, col_source, col_target, copy_columns)
            for target_col, source_col in copy_column_map.items():
                if source_col in col_source and target_col in col_target:
                    val = row_vals.get(source_col)
                    ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")
            continue
        rows_with_keys.append((row_idx, query))
    return rows_with_keys


def _write_row_extraction(
    ws_source,
    ws_target,
    row_idx: int,
    row_vals: dict[str, Any],
    mapping: dict[str, Any],
    col_source: dict[str, int],
    col_target: dict[str, int],
    target_columns: list[str],
    copy_columns: list[str],
    copy_column_map: dict[str, str],
) -> tuple[bool, dict[str, Any] | None]:
    """Copy columns and write extracted values. Returns (row_updated, error_dict or None)."""
    copy_row_columns(ws_source, ws_target, row_idx, col_source, col_target, copy_columns)
    for target_col, source_col in copy_column_map.items():
        if source_col in col_source and target_col in col_target:
            val = row_vals.get(source_col)
            ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")
    if not mapping:
        return (False, {"row": row_idx, "key": "", "reason": "No mapping"})
    row_updated = False
    for col in target_columns:
        if col not in col_target:
            continue
        val = mapping.get(col)
        if val is None:
            val = ""
        ws_target.cell(row=row_idx, column=col_target[col], value=val)
        row_updated = True
    return (row_updated, None)


def _save_and_format_output(
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


async def run_fill_workflow(
    args: dict,
    ctx: ResolvedContext,
    wb,
    ws_source,
    ws_target,
    col_source: dict[str, int],
    col_target: dict[str, int],
    full_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    """Execute fill workflow."""
    parsed = _parse_fill_args(args)
    key_column = parsed["key_column"]
    company_column = parsed["company_column"]
    target_columns = parsed["target_columns"]
    copy_columns = parsed["copy_columns"]
    copy_column_map = parsed["copy_column_map"]
    start_row = parsed["start_row"]
    max_rows = parsed["max_rows"]
    batch_size = parsed["batch_size"]
    mode = parsed["mode"]
    instructions = parsed["instructions"]
    retrieve_mode = parsed["retrieve_mode"]

    if err := _validate_fill_columns(col_source, col_target, key_column, company_column, copy_column_map):
        return err

    headers_target = extract_headers(ws_target)
    col_target = _ensure_target_columns(
        ws_target, headers_target, col_target,
        target_columns, copy_columns, copy_column_map,
    )

    range_result = _compute_row_range(ws_source, start_row, max_rows)
    if isinstance(range_result, dict):
        return range_result
    start_row, end_row = range_result

    rows_with_keys = _collect_rows_with_keys(
        ws_source, ws_target, col_source, col_target,
        start_row, end_row, key_column, company_column,
        copy_columns, copy_column_map,
    )

    logger.info("[fill_by_column] path=%s rows=%d batch_size=%d", args.get("path"), len(rows_with_keys), batch_size)
    emit(
        "progress",
        phase="fill_by_column_start",
        total=len(rows_with_keys),
        display_text=f"Processing {len(rows_with_keys)} rows",
    )

    ctx_dict = {
        "workspace_root": ctx.workspace_root,
        "session_id": ctx.session_id,
        "user_id": ctx.user_id,
        "db_path": ctx.db_path,
        "call_stack": ctx.call_stack,
    }
    provider = get_provider()
    processed_rows = 0
    updated_rows = 0
    errors: list[dict[str, Any]] = []

    i = 0
    while i < len(rows_with_keys):
        batch_slice = rows_with_keys[i : i + batch_size]
        i += batch_size
        row_indices = [t[0] for t in batch_slice]
        keys = [t[1] for t in batch_slice]

        contents = await retrieve_batch(
            keys,
            execute_with_events,
            ctx_dict,
            project_root,
            search_num=SEARCH_NUM_RESULTS,
            retrieve_mode=retrieve_mode,
        )
        items = [(k, contents.get(k, "")) for k in keys]
        extracted = await extract_batch(
            items, target_columns, instructions, provider,
            content_preview_len=CONTENT_PREVIEW_LEN,
        )

        for j, row_idx in enumerate(row_indices):
            processed_rows += 1
            row_vals = read_row(ws_source, row_idx, col_source)
            mapping = extracted[j] if j < len(extracted) and isinstance(extracted[j], dict) else {}
            row_updated, err = _write_row_extraction(
                ws_source, ws_target, row_idx, row_vals, mapping or {},
                col_source, col_target, target_columns, copy_columns, copy_column_map,
            )
            if err:
                err["key"] = keys[j][:80] if j < len(keys) else ""
                errors.append(err)
            elif row_updated:
                updated_rows += 1

        emit("progress", phase="batch", processed=processed_rows, total=len(rows_with_keys))

    output_path_str = _save_and_format_output(wb, full_path, mode, ctx.workspace_root)

    result: dict[str, Any] = {
        "output_path": output_path_str,
        "processed_rows": processed_rows,
        "updated_rows": updated_rows,
        "target_columns": target_columns,
    }
    if copy_columns:
        result["copy_columns"] = copy_columns
    if copy_column_map:
        result["copy_column_map"] = copy_column_map
    if errors:
        result["errors"] = errors
    return result
