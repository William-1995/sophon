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
    MODE_OVERWRITE,
    OUTPUT_SUFFIX_ENRICHED,
    OUTPUT_SUFFIX_FILLED,
    RETRIEVE_MODE_DEFAULT,
    SEARCH_NUM_RESULTS,
    START_ROW_DATA_DEFAULT,
)
from _context import resolve_context, resolve_path as resolve_path_util
from _excel import (
    build_column_index,
    ensure_columns_exist,
    extract_headers,
    load_sheet,
)
from _extract import extract_batch
from _file_io import determine_output_path, resolve_full_path
from _retrieve import retrieve_batch
from _search import build_search_query

logger = logging.getLogger(__name__)


async def _run_async(params: dict) -> dict[str, Any]:
    args = params.get("arguments") or params
    path_raw = str(args.get("path", "")).strip()
    key_column = str(args.get("key_column") or args.get("id_column", "")).strip()
    company_column = args.get("company_column")
    target_columns = args.get("target_columns") or []
    copy_columns = args.get("copy_columns") or []
    copy_column_map = args.get("copy_column_map") or {}
    if not isinstance(copy_column_map, dict):
        copy_column_map = {}
    source_sheet = args.get("source_sheet") or args.get("sheet_name")
    target_sheet = args.get("target_sheet") or source_sheet
    start_row = int(args.get("start_row", START_ROW_DATA_DEFAULT))
    max_rows = args.get("max_rows")
    batch_size = int(args.get("batch_size", DEFAULT_BATCH_SIZE))
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    mode = str(args.get("mode", MODE_COPY)).strip().lower() or MODE_COPY
    instructions = str(args.get("instructions", "")).strip()
    retrieve_mode = str(args.get("retrieve_mode", RETRIEVE_MODE_DEFAULT)).strip().lower() or RETRIEVE_MODE_DEFAULT

    if not path_raw:
        logger.warning("[excel-ops.fill_by_column] missing path")
        return {"error": "path is required"}
    if not key_column:
        logger.warning("[excel-ops.fill_by_column] missing key_column")
        return {"error": "key_column is required"}
    if not isinstance(target_columns, list) or not target_columns:
        logger.warning("[excel-ops.fill_by_column] target_columns empty")
        return {"error": "target_columns must be a non-empty list of column names"}

    ctx = resolve_context(params)
    full_path = resolve_path_util(params, path_raw)

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

    all_cols_to_ensure = list(target_columns) + list(copy_columns or []) + list(copy_column_map.keys())
    headers_target, col_target = ensure_columns_exist(ws_target, headers_target, col_target, all_cols_to_ensure)

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

    rows_with_keys: list[tuple[int, str]] = []
    for row_idx in range(start_row, end_row + 1):
        row_vals = read_row(ws_source, row_idx, col_source)
        query = build_search_query(row_vals, key_column, company_column)
        if not query:
            copy_row_columns(ws_source, ws_target, row_idx, col_source, col_target, copy_columns or [])
            for target_col, source_col in copy_column_map.items():
                if source_col in col_source and target_col in col_target:
                    val = row_vals.get(source_col)
                    ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")
            continue
        rows_with_keys.append((row_idx, query))

    logger.info(
        "[excel-ops.fill_by_column] path=%s key_column=%s target_columns=%s rows=%d batch_size=%d retrieve_mode=%s",
        path_raw,
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

    provider = get_provider()
    processed_rows = 0
    updated_rows = 0
    errors: list[dict[str, Any]] = []

    ctx_dict = {
        "workspace_root": ctx.workspace_root,
        "session_id": ctx.session_id,
        "user_id": ctx.user_id,
        "db_path": ctx.db_path,
        "call_stack": ctx.call_stack,
    }

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
            copy_row_columns(ws_source, ws_target, row_idx, col_source, col_target, copy_columns or [])
            for target_col, source_col in copy_column_map.items():
                if source_col in col_source and target_col in col_target:
                    val = row_vals.get(source_col)
                    ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")
            mapping = extracted[j] if j < len(extracted) and isinstance(extracted[j], dict) else {}
            if not mapping:
                errors.append({"row": row_idx, "key": keys[j][:80], "reason": "No mapping from LLM"})
                continue
            row_updated = False
            for col in target_columns:
                if col not in col_target:
                    continue
                val = mapping.get(col)
                if val is None:
                    val = ""
                ws_target.cell(row=row_idx, column=col_target[col], value=val)
                row_updated = True
            if row_updated:
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

    out_path = determine_output_path(full_path, mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)

    output_path_str = str(out_path)
    if output_path_str.startswith(str(ctx.workspace_root)):
        output_path_str = str(out_path.relative_to(ctx.workspace_root))

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
