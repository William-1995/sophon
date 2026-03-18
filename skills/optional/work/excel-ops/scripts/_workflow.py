"""
Excel-Ops Enrich - Workflow orchestration.

Main workflow coordination for enrichment operations.
"""

import logging
from pathlib import Path
from typing import Any

from _batch import process_batch
from _config import SEARCH_NUM_RESULTS
from _context import ResolvedContext
from _excel import (
    build_column_index,
    ensure_columns_exist,
    extract_headers,
    load_sheet,
)
from _file_io import determine_output_path, resolve_full_path
from providers import get_provider

logger = logging.getLogger(__name__)


def validate_params(args: dict) -> dict | None:
    """Validate input parameters."""
    if not args.get("path"):
        return {"error": "path is required"}
    if not args.get("id_column"):
        return {"error": "id_column is required"}
    target_columns = args.get("target_columns")
    if not isinstance(target_columns, list) or not target_columns:
        return {"error": "target_columns must be a non-empty array"}
    return None


def setup_worksheets(
    args: dict, ctx: ResolvedContext
) -> tuple[Any, Any, Any, Path, dict | None]:
    """Load workbook and setup worksheets."""
    full_path = resolve_full_path(str(args.get("path", "")).strip(), ctx)
    source_sheet = args.get("source_sheet") or args.get("sheet_name")
    target_sheet = args.get("target_sheet") or source_sheet

    sheet_tuple, err = load_sheet(full_path, source_sheet)
    if err:
        return None, None, None, full_path, err

    wb, ws_source = sheet_tuple

    # Handle cross-sheet
    if source_sheet != target_sheet:
        if target_sheet not in wb.sheetnames:
            return (
                None,
                None,
                None,
                full_path,
                {
                    "error": f"target_sheet '{target_sheet}' not found. Available: {wb.sheetnames}"
                },
            )
        ws_target = wb[target_sheet]
    else:
        ws_target = ws_source

    return wb, ws_source, ws_target, full_path, None


def validate_columns(
    ws_source,
    ws_target,
    id_column: str,
    company_column: str | None,
    target_columns: list[str],
    copy_columns: list[str],
) -> tuple[dict[str, int], dict[str, int], dict | None]:
    """Extract and validate column headers."""
    headers_source = extract_headers(ws_source)
    if not headers_source:
        return None, None, {"error": "Source sheet header row is empty"}

    col_index_source = build_column_index(headers_source)

    if id_column not in col_index_source:
        return None, None, {
            "error": f"id_column '{id_column}' not found in headers: {headers_source}"
        }

    if company_column and company_column not in col_index_source:
        return None, None, {"error": f"company_column '{company_column}' not found"}

    headers_target = extract_headers(ws_target)
    if not headers_target:
        return None, None, {"error": "Target sheet header row is empty"}

    col_index_target = build_column_index(headers_target)

    # Ensure target columns exist
    headers_target, col_index_target = ensure_columns_exist(
        ws_target,
        headers_target,
        col_index_target,
        list(target_columns) + list(copy_columns or []),
    )

    return col_index_source, col_index_target, None


def calculate_row_range(ws_source, start_row: int, max_rows):
    """Calculate start and end row for processing."""
    max_row = ws_source.max_row

    if max_rows is not None:
        try:
            max_rows_int = int(max_rows)
            end_row = min(start_row + max_rows_int - 1, max_row)
        except (TypeError, ValueError):
            return None, {"error": f"Invalid max_rows: {max_rows!r}"}
    else:
        end_row = max_row

    if start_row < 2:
        start_row = 2
    if start_row > end_row:
        return None, {"error": f"Empty range: start_row={start_row}, end_row={end_row}"}

    return (start_row, end_row), None


async def run_enrichment_workflow(
    args: dict,
    ctx: ResolvedContext,
    wb,
    ws_source,
    ws_target,
    full_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    """Execute the enrichment workflow."""
    # Extract parameters
    id_column = str(args.get("id_column", "")).strip()
    company_column = args.get("company_column")
    target_columns = args.get("target_columns") or []
    copy_columns = args.get("copy_columns") or []
    instructions = str(args.get("instructions", "")).strip()
    start_row = int(args.get("start_row", 2))
    max_rows = args.get("max_rows")
    batch_size = int(args.get("batch_size", 5))
    mode = str(args.get("mode", "copy")).strip().lower() or "copy"

    # Validate columns
    col_index_source, col_index_target, err = validate_columns(
        ws_source, ws_target, id_column, company_column, target_columns, copy_columns
    )
    if err:
        return err

    # Calculate row range
    row_range, err = calculate_row_range(ws_source, start_row, max_rows)
    if err:
        return err
    start_row, end_row = row_range

    # Initialize
    provider = get_provider()
    processed_rows = 0
    updated_rows = 0
    errors: list[dict[str, Any]] = []

    # Process batches
    current = start_row
    while current <= end_row:
        batch_end = min(current + batch_size - 1, end_row)
        row_indices = list(range(current, batch_end + 1))

        batch_updated, batch_errors = await process_batch(
            row_indices=row_indices,
            ws_source=ws_source,
            ws_target=ws_target,
            col_index_source=col_index_source,
            col_index_target=col_index_target,
            target_columns=target_columns,
            id_column=id_column,
            company_column=company_column,
            copy_columns=copy_columns,
            instructions=instructions,
            provider=provider,
            ctx=ctx,
            project_root=project_root,
            search_num=SEARCH_NUM_RESULTS,
        )

        processed_rows += len(row_indices)
        updated_rows += batch_updated
        errors.extend(batch_errors)
        current = batch_end + 1

    # Save
    out_path = determine_output_path(full_path, mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)

    # Build result
    result: dict[str, Any] = {
        "output_path": str(
            out_path.relative_to(ctx.workspace_root)
            if str(out_path).startswith(str(ctx.workspace_root))
            else out_path
        ),
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
        processed_rows,
        len(errors),
        result.get("output_path", ""),
    )

    return result
