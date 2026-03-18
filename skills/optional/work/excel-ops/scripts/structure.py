#!/usr/bin/env python3
"""
excel-ops/structure action.

Understand Excel structure: sheets, headers, sample rows.
Uses excel.list_sheets and excel.read internally (not exposed to LLM).
Named 'structure' to avoid shadowing Python's stdlib 'inspect' module.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _context import resolve_context
from core.executor import execute_skill

logger = logging.getLogger(__name__)


async def _structure_async(params: dict) -> dict:
    args = params.get("arguments") or params
    path = str(args.get("path", "")).strip()
    sheet_name = args.get("sheet_name")
    source_sheet = args.get("source_sheet")
    target_sheet = args.get("target_sheet")
    sample_rows = int(args.get("sample_rows", 5))

    if not path:
        return {"error": "path is required"}

    ctx = resolve_context(params)

    # 1. List sheets (via excel skill)
    list_result = await execute_skill(
        skill_name="excel",
        action="list_sheets",
        arguments={"file": path},
        workspace_root=ctx.workspace_root,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
        root=_PROJECT_ROOT,
        db_path=ctx.db_path if ctx.db_path.exists() else None,
        call_stack=ctx.call_stack,
    )
    if list_result.get("error"):
        return list_result
    all_sheets = list_result.get("sheets") or []
    if not all_sheets:
        return {"sheets": [], "sheets_detail": {}, "error": "No sheets found"}

    # 2. Determine which sheets to read
    if source_sheet and target_sheet:
        # Cross-sheet: read both source and target (1-2 sample rows each)
        for s in (source_sheet, target_sheet):
            if s not in all_sheets:
                return {"error": f"Sheet '{s}' not found. Available: {all_sheets}"}
        sheets = list(dict.fromkeys([source_sheet, target_sheet]))
        sample_rows = min(sample_rows, 2)  # 1-2 rows for cross-sheet context
    elif sheet_name:
        if sheet_name not in all_sheets:
            return {"error": f"Sheet '{sheet_name}' not found. Available: {all_sheets}"}
        sheets = [sheet_name]
    else:
        sheets = all_sheets

    # 3. Read each sheet (sample rows)
    sheets_detail = {}
    for sheet in sheets:
        read_result = await execute_skill(
            skill_name="excel",
            action="read",
            arguments={"file": path, "sheet": sheet, "limit": sample_rows, "offset": 0},
            workspace_root=ctx.workspace_root,
            session_id=ctx.session_id,
            user_id=ctx.user_id,
            root=_PROJECT_ROOT,
            db_path=ctx.db_path if ctx.db_path.exists() else None,
            call_stack=ctx.call_stack,
        )
        if read_result.get("error"):
            sheets_detail[sheet] = {"error": read_result["error"]}
        else:
            sheets_detail[sheet] = {
                "headers": read_result.get("headers", []),
                "data": read_result.get("data", []),
                "total_rows": read_result.get("total_rows", 0),
            }

    return {"sheets": list(list_result.get("sheets") or []), "sheets_detail": sheets_detail}


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_structure_async(params))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
