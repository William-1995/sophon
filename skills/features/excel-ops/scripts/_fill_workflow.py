"""
Excel-Ops FillByColumn - Main workflow.

Fill column workflow orchestration.
"""

import logging
from pathlib import Path
from typing import Any

from _config import (
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
from _context import ResolvedContext, resolve_path
from _events import emit, execute_with_events
from _excel import build_column_index, extract_headers, load_sheet
from _extract import extract_batch
from _retrieve import retrieve_batch
from _search import build_search_query
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
    full_path = resolve_path(ctx, str(args.get("path", "")).strip())
    source_sheet = args.get("source_sheet") or args.get("sheet_name")
    target_sheet = args.get("target_sheet") or source_sheet

    sheet_tuple, err = load_sheet(full_path, source_sheet)
    if err:
        return None, None, None, None, full_path, err

    wb, ws_source = sheet_tuple

    # Handle cross-sheet
    if source_sheet != target_sheet:
        if target_sheet not in wb.sheetnames:
            return (
                None, None, None, None, full_path,
                {"error": f"target_sheet '{target_sheet}' not found"}
            )
        ws_target = wb[target_sheet]
    else:
        ws_target = ws_source

    # Build column indices
    col_source = build_column_index(extract_headers(ws_source))
    col_target = build_column_index(extract_headers(ws_target))

    return wb, ws_source, ws_target, col_source, col_target, full_path, None


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
    # Extract parameters
    key_column = str(args.get("key_column") or args.get("id_column", "")).strip()
    company_column = args.get("company_column")
    target_columns = args.get("target_columns") or []
    copy_columns = args.get("copy_columns") or []
    copy_column_map = args.get("copy_column_map") or {}
    if not isinstance(copy_column_map, dict):
        copy_column_map = {}

    start_row = int(args.get("start_row", START_ROW_DATA_DEFAULT))
    max_rows = args.get("max_rows")
    batch_size = int(args.get("batch_size", DEFAULT_BATCH_SIZE))
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    mode = str(args.get("mode", MODE_COPY)).strip().lower() or MODE_COPY
    instructions = str(args.get("instructions", "")).strip()
    retrieve_mode = str(args.get("retrieve_mode", RETRIEVE_MODE_DEFAULT)).strip().lower() or RETRIEVE_MODE_DEFAULT

    # Validate columns
    if key_column not in col_source:
        return {"error": f"key_column '{key_column}' not in source headers"}
    if company_column and company_column not in col_source:
        return {"error": f"company_column '{company_column}' not found"}

    # Ensure target columns exist
    for col in list(target_columns) + list(copy_columns or []) + list(copy_column_map.keys()):
        if col not in col_target:
            col_target[col] = len(col_target) + 1
            ws_target.cell(row=1, column=col_target[col], value=col)

    # Calculate row range
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

    # Read rows with keys
    def read_row(row_idx: int) -> dict[str, Any]:
        return {
            name: ws_source.cell(row=row_idx, column=idx).value
            for name, idx in col_source.items()
        }

    def copy_row_to_target(row_idx: int, row_vals: dict[str, Any]) -> None:
        for col in copy_columns or []:
            if col not in col_source or col not in col_target:
                continue
            val = row_vals.get(col)
            ws_target.cell(row=row_idx, column=col_target[col], value=val if val is not None else "")
        for target_col, source_col in copy_column_map.items():
            if source_col not in col_source or target_col not in col_target:
                continue
            val = row_vals.get(source_col)
            ws_target.cell(row=row_idx, column=col_target[target_col], value=val if val is not None else "")

    rows_with_keys: list[tuple[int, str]] = []
    for row_idx in range(start_row, end_row + 1):
        row_vals = read_row(row_idx)
        query = build_search_query(row_vals, key_column, company_column)
        if not query:
            copy_row_to_target(row_idx, row_vals)
            continue
        rows_with_keys.append((row_idx, query))

    logger.info(
        "[fill_by_column] path=%s rows=%d batch_size=%d",
        args.get("path"), len(rows_with_keys), batch_size
    )
    emit(
        "progress",
        phase="fill_by_column_start",
        total=len(rows_with_keys),
        display_text=f"Processing {len(rows_with_keys)} rows",
    )

    # Process batches
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
            {
                "workspace_root": ctx.workspace_root,
                "session_id": ctx.session_id,
                "user_id": ctx.user_id,
                "db_path": ctx.db_path,
                "call_stack": ctx.call_stack,
            },
            project_root,
            search_num=SEARCH_NUM_RESULTS,
            retrieve_mode=retrieve_mode,
        )

        items = [(k, contents.get(k, "")) for k in keys]
        extracted = await extract_batch(
            items, target_columns, instructions, provider
        )

        for j, row_idx in enumerate(row_indices):
            processed_rows += 1
            row_vals = read_row(row_idx)
            copy_row_to_target(row_idx, row_vals)

            mapping = extracted[j] if j < len(extracted) and isinstance(extracted[j], dict) else {}
            if not mapping:
                errors.append({"row": row_idx, "key": keys[j][:80], "reason": "No mapping"})
                continue

            row_updated = False
            for col in target_columns:
                if col not in col_target:
                    continue
                val = mapping.get(col, "")
                ws_target.cell(row=row_idx, column=col_target[col], value=val)
                row_updated = True

            if row_updated:
                updated_rows += 1

        emit(
            "progress",
            phase="batch",
            processed=processed_rows,
            total=len(rows_with_keys),
        )

    # Save
    if mode == MODE_OVERWRITE:
        out_path = full_path
    else:
        stem = full_path.stem
        suffix = full_path.suffix
        out_name = (
            f"{stem}{OUTPUT_SUFFIX_ENRICHED}{suffix}"
            if stem.endswith(OUTPUT_SUFFIX_FILLED)
            else f"{stem}{OUTPUT_SUFFIX_FILLED}{suffix}"
        )
        out_path = full_path.with_name(out_name)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)

    # Build result
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

    return result
