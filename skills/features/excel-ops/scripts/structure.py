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

_project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "excel_ops_constants",
    Path(__file__).resolve().parent.parent / "constants.py",
)
_c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c)
DB_FILENAME = _c.DB_FILENAME  # type: ignore
from core.executor import execute_skill  # type: ignore

logger = logging.getLogger(__name__)


def _resolve_params(params: dict) -> dict:
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    session_id = str(params.get("_executor_session_id") or params.get("session_id") or "default")
    user_id = str(params.get("user_id") or "default_user")
    db_path_raw = params.get("db_path")
    db_path = Path(db_path_raw) if db_path_raw else workspace_root / DB_FILENAME
    call_stack = list(params.get("_call_stack") or [])
    return {
        "workspace_root": workspace_root,
        "session_id": session_id,
        "user_id": user_id,
        "db_path": db_path,
        "call_stack": call_stack,
    }


async def _structure_async(params: dict) -> dict:
    args = params.get("arguments") or params
    path = str(args.get("path", "")).strip()
    sheet_name = args.get("sheet_name")
    source_sheet = args.get("source_sheet")
    target_sheet = args.get("target_sheet")
    sample_rows = int(args.get("sample_rows", 5))

    if not path:
        return {"error": "path is required"}

    resolved = _resolve_params(params)
    workspace_root = resolved["workspace_root"]
    session_id = resolved["session_id"]
    user_id = resolved["user_id"]
    db_path = resolved["db_path"]
    call_stack = resolved["call_stack"]

    # 1. List sheets (via excel skill)
    list_result = await execute_skill(
        skill_name="excel",
        action="list_sheets",
        arguments={"file": path},
        workspace_root=workspace_root,
        session_id=session_id,
        user_id=user_id,
        root=_project_root,
        db_path=db_path if db_path.exists() else None,
        call_stack=call_stack,
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
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            root=_project_root,
            db_path=db_path if db_path.exists() else None,
            call_stack=call_stack,
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
