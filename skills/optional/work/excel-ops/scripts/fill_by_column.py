#!/usr/bin/env python3
"""
excel-ops/fill_by_column action.

Generic pipeline: read key column from sheet(s), batch parallel retrieve (search),
LLM extract per batch, write back by row. Keys (e.g. URLs) identify rows for writing.

Refactored to use shared modules: _context, _excel, _batch, _events, _search, _file_io.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from providers import get_provider

from _batch import copy_row_columns, read_row
from _events import emit_progress, execute_with_events
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
from _context import ResolvedContext, resolve_context, resolve_path as resolve_path_util
from _excel import (
    build_column_index,
    ensure_columns_exist,
    extract_headers,
    load_sheet,
)
from _extract import extract_batch
from _file_io import determine_output_path
from _retrieve import retrieve_batch
from _search import build_search_query

logger = logging.getLogger(__name__)


def _parse_args(params: dict) -> dict[str, Any]:
    """Parse and normalize arguments from params."""
    args = params.get("arguments") or params
    batch_size = int(args.get("batch_size", DEFAULT_BATCH_SIZE))
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    copy_column_map = args.get("copy_column_map") or {}
    if not isinstance(copy_column_map, dict):
        copy_column_map = {}
    source_sheet = args.get("source_sheet") or args.get("sheet_name")
    return {
        "path_raw": str(args.get("path", "")).strip(),
        "key_column": str(args.get("key_column") or args.get("id_column", "")).strip(),
        "company_column": args.get("company_column"),
        "target_columns": args.get("target_columns") or [],
        "copy_columns": args.get("copy_columns") or [],
        "copy_column_map": copy_column_map,
        "source_sheet": source_sheet,
        "target_sheet": args.get("target_sheet") or source_sheet,
        "start_row": int(args.get("start_row", START_ROW_DATA_DEFAULT)),
        "max_rows": args.get("max_rows"),
        "batch_size": batch_size,
        "mode": str(args.get("mode", MODE_COPY)).strip().lower() or MODE_COPY,
        "instructions": str(args.get("instructions", "")).strip(),
        "retrieve_mode": str(args.get("retrieve_mode", RETRIEVE_MODE_DEFAULT)).strip().lower()
        or RETRIEVE_MODE_DEFAULT,
    }


def _validate_args(args: dict[str, Any]) -> dict[str, Any] | None:
    """Validate required arguments. Returns error dict or None."""
    if not args.get("path_raw"):
        logger.warning("[excel-ops.fill_by_column] missing path")
        return {"error": "path is required"}
    if not args.get("key_column"):
        logger.warning("[excel-ops.fill_by_column] missing key_column")
        return {"error": "key_column is required"}
    target_columns = args.get("target_columns") or []
    if not isinstance(target_columns, list) or not target_columns:
        logger.warning("[excel-ops.fill_by_column] target_columns empty")
        return {"error": "target_columns must be a non-empty list of column names"}
    return None


def _load_workbook_and_sheets(
    full_path: Path,
    source_sheet: str,
    target_sheet: str,
) -> tuple[Any, Any, Any] | dict[str, Any]:
    """Load workbook and resolve source/target worksheets. Returns (wb, ws_source, ws_target) or error."""
    (wb, ws_source), err = load_sheet(full_path, source_sheet)
    if err:
        return err
    cross_sheet = source_sheet != target_sheet
    if cross_sheet:
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
) -> tuple[dict[str, int], dict[str, int], list[str]] | dict[str, Any]:
    """Build column indices, validate, ensure target columns. Returns (col_source, col_target, headers_target) or error."""
    key_column = args["key_column"]
    company_column = args.get("company_column")
    copy_column_map = args.get("copy_column_map") or {}
    target_columns = args["target_columns"]
    copy_columns = args.get("copy_columns") or []

    headers_source = extract_headers(ws_source)
    headers_target = extract_headers(ws_target)
    col_source = build_column_index(headers_source)
    col_target = build_column_index(headers_target)

    if key_column not in col_source:
        return {"error": f"key_column '{key_column}' not in source headers: {headers_source}"}
    if company_column and company_column not in col_source:
        return {"error": f"company_column '{company_column}' not in source headers"}
    for target_col, source_col in copy_column_map.items():
        if source_col not in col_source:
            return {"error": f"copy_column_map target '{target_col}' maps from source column '{source_col}' which is not in source headers"}

    all_cols_to_ensure = list(target_columns) + list(copy_columns) + list(copy_column_map.keys())
    headers_target, col_target = ensure_columns_exist(
        ws_target, headers_target, col_target, all_cols_to_ensure
    )
    return (col_source, col_target, headers_target)


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
    """Collect (row_idx, query) for rows that have a search query. Copy-only rows are handled inline."""
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
    """Copy columns and write extracted values to target row. Returns (row_updated, error_dict or None)."""
    copy_row_columns(ws_source, ws_target, row_idx, col_source, col_target, copy_columns)
    for target_col, source_col in copy_column_map.items():
        if source_col in col_source and target_col in col_target:
            val = row_vals.get(source_col)
            ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")
    if not mapping:
        return (False, {"row": row_idx, "key": "", "reason": "No mapping from LLM"})
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
    output_path_str = str(out_path)
    if output_path_str.startswith(str(workspace_root)):
        output_path_str = str(out_path.relative_to(workspace_root))
    return output_path_str


async def _run_async(params: dict) -> dict[str, Any]:
    args = _parse_args(params)
    if err := _validate_args(args):
        return err

    ctx: ResolvedContext = resolve_context(params)
    full_path = resolve_path_util(params, args["path_raw"])
    source_sheet = args["source_sheet"]
    target_sheet = args["target_sheet"]

    load_result = _load_workbook_and_sheets(full_path, source_sheet, target_sheet)
    if isinstance(load_result, dict):
        return load_result
    wb, ws_source, ws_target = load_result

    col_result = _prepare_columns(ws_source, ws_target, args)
    if isinstance(col_result, dict):
        return col_result
    col_source, col_target, _ = col_result

    range_result = _compute_row_range(ws_source, args["start_row"], args["max_rows"])
    if isinstance(range_result, dict):
        return range_result
    start_row, end_row = range_result

    rows_with_keys = _collect_rows_with_keys(
        ws_source,
        ws_target,
        col_source,
        col_target,
        start_row,
        end_row,
        args["key_column"],
        args.get("company_column"),
        args["copy_columns"],
        args["copy_column_map"],
    )

    key_column = args["key_column"]
    target_columns = args["target_columns"]
    batch_size = args["batch_size"]
    retrieve_mode = args["retrieve_mode"]
    instructions = args["instructions"]
    copy_columns = args["copy_columns"]
    copy_column_map = args["copy_column_map"]
    mode = args["mode"]

    logger.info(
        "[excel-ops.fill_by_column] path=%s key_column=%s target_columns=%s rows=%d batch_size=%d retrieve_mode=%s",
        args["path_raw"],
        key_column,
        target_columns,
        len(rows_with_keys),
        batch_size,
        retrieve_mode,
    )
    emit_progress(
        "progress",
        phase="fill_by_column_start",
        total=len(rows_with_keys),
        key_column=key_column,
        display_text=f"Filling column {key_column}, {len(rows_with_keys)} rows to process",
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
            _PROJECT_ROOT,
            search_num=SEARCH_NUM_RESULTS,
            retrieve_mode=retrieve_mode,
        )
        items = [(k, contents.get(k, "")) for k in keys]
        extracted = await extract_batch(
            items,
            target_columns,
            instructions,
            provider,
            content_preview_len=CONTENT_PREVIEW_LEN,
        )

        for j, row_idx in enumerate(row_indices):
            processed_rows += 1
            row_vals = read_row(ws_source, row_idx, col_source)
            mapping = extracted[j] if j < len(extracted) and isinstance(extracted[j], dict) else {}
            row_updated, err = _write_row_extraction(
                ws_source,
                ws_target,
                row_idx,
                row_vals,
                mapping or {},
                col_source,
                col_target,
                target_columns,
                copy_columns,
                copy_column_map,
            )
            if err:
                err["key"] = keys[j][:80] if j < len(keys) else ""
                errors.append(err)
            elif row_updated:
                updated_rows += 1
                logger.debug("[excel-ops.fill_by_column] row=%d written", row_idx)

        emit_progress(
            "progress",
            phase="batch",
            processed=processed_rows,
            total=len(rows_with_keys),
            batch_size=len(batch_slice),
            display_text=f"Filling column {key_column}, processed {processed_rows}/{len(rows_with_keys)} rows",
        )

    output_path_str = _save_workbook_and_format_output(wb, full_path, mode, ctx.workspace_root)

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

    logger.info(
        "[excel-ops.fill_by_column] done processed=%d updated=%d errors=%d output_path=%s",
        processed_rows,
        updated_rows,
        len(errors),
        result["output_path"],
    )
    return result


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_async(params))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
