#!/usr/bin/env python3
"""
excel-ops/list_sheets action.

Returns sheet names in the workbook. LLM uses this to choose which sheets to read.
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

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "excel_ops_constants",
    Path(__file__).resolve().parent.parent / "constants.py",
)
_c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c)
DB_FILENAME = _c.DB_FILENAME
from core.executor import execute_skill

from _config import DEPENDENCY_SKILL_EXCEL

logger = logging.getLogger(__name__)


def _resolve_path(params: dict, path_raw: str) -> Path:
    p = Path(path_raw.strip())
    if p.is_absolute():
        return p
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    user_id = str(params.get("user_id") or "default_user")
    if p.parts and p.parts[0] == user_id:
        p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path(".")
    return (workspace_root / p).resolve()


def _resolve_context(params: dict) -> dict:
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    session_id = str(params.get("_executor_session_id") or params.get("session_id") or "default")
    user_id = str(params.get("user_id") or "default_user")
    db_path = params.get("db_path")
    db_path = Path(db_path) if db_path else workspace_root / DB_FILENAME
    call_stack = list(params.get("_call_stack") or [])
    return {
        "workspace_root": workspace_root,
        "session_id": session_id,
        "user_id": user_id,
        "db_path": db_path,
        "call_stack": call_stack,
    }


async def _run_async(params: dict) -> dict:
    args = params.get("arguments") or params
    path_raw = str(args.get("path", "")).strip()
    if not path_raw:
        logger.warning("[excel-ops.list_sheets] missing path")
        return {"error": "path is required"}

    ctx = _resolve_context(params)
    full_path = _resolve_path(params, path_raw)
    if not full_path.exists():
        logger.warning("[excel-ops.list_sheets] file_not_found path=%s", full_path)
        return {"error": f"File not found: {full_path}"}

    result = await execute_skill(
        skill_name=DEPENDENCY_SKILL_EXCEL,
        action="list_sheets",
        arguments={"file": path_raw},
        workspace_root=ctx["workspace_root"],
        session_id=ctx["session_id"],
        user_id=ctx["user_id"],
        root=_PROJECT_ROOT,
        db_path=ctx["db_path"] if ctx["db_path"].exists() else None,
        call_stack=ctx["call_stack"],
    )
    if result.get("error"):
        logger.warning("[excel-ops.list_sheets] excel.list_sheets error=%s", result["error"])
        return result
    sheets = result.get("sheets") or []
    logger.info("[excel-ops.list_sheets] path=%s sheets_count=%d", path_raw, len(sheets))
    return {"sheets": sheets}


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_async(params))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
