#!/usr/bin/env python3
"""
excel-ops/read_structure action.

Returns one sheet's headers and total row count (no data). Uses excel.structure primitive.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _config import DEPENDENCY_SKILL_EXCEL
from _context import resolve_context
from core.executor import execute_skill

logger = logging.getLogger(__name__)


async def _run_async(params: dict) -> dict:
    args = params.get("arguments") or params
    path_raw = str(args.get("path", "")).strip()
    sheet_name = args.get("sheet_name") or args.get("sheet")

    if not path_raw:
        logger.warning("[excel-ops.read_structure] missing path")
        return {"error": "path is required"}

    ctx = resolve_context(params)
    full_path = (ctx.workspace_root / path_raw).resolve()
    if not full_path.exists():
        return {"error": f"File not found: {path_raw}"}

    result = await execute_skill(
        skill_name=DEPENDENCY_SKILL_EXCEL,
        action="structure",
        arguments={"file": path_raw, "sheet": sheet_name},
        workspace_root=ctx.workspace_root,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
        root=_PROJECT_ROOT,
        db_path=ctx.db_path if ctx.db_path.exists() else None,
        call_stack=ctx.call_stack,
    )
    if result.get("error"):
        logger.warning("[excel-ops.read_structure] excel.structure error=%s", result["error"])
        return result
    logger.info(
        "[excel-ops.read_structure] path=%s sheet=%s headers_count=%d total_rows=%d",
        path_raw,
        result.get("sheet", ""),
        len(result.get("headers", [])),
        result.get("total_rows", 0),
    )
    return result


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_async(params))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
