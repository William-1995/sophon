#!/usr/bin/env python3
"""Filesystem delete - delete file(s). Two-phase: first list files for confirmation, then delete."""
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

logger = logging.getLogger(__name__)

try:
    from constants import (
        CANCEL_CHOICE,
        CONFIRM_CHOICE,
        DECISION_REQUEST_KEY,
        DELETE_PARALLEL_WORKERS,
    )
except ImportError:
    CANCEL_CHOICE = "Cancel"
    CONFIRM_CHOICE = "Confirm"
    DECISION_REQUEST_KEY = "__decision_request"
    DELETE_PARALLEL_WORKERS = 8


def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def _delete_one(
    workspace_root: Path,
    f: str,
) -> dict:
    """Delete single file; used for parallel batch."""
    if not isinstance(f, str):
        return {"path": str(f), "error": "Invalid path type"}
    target = workspace_root / f
    if not target.exists():
        return {"path": f, "error": f"File not found: {f}"}
    if not target.is_file():
        return {"path": f, "error": "Cannot delete directory, only files supported"}
    if not _ensure_in_workspace(workspace_root, target):
        return {"path": f, "error": "Path cannot escape workspace"}
    try:
        target.unlink()
        return {"path": f, "success": True}
    except Exception as e:
        return {"path": f, "error": f"Delete failed: {str(e)}"}


def _validate_and_collect_files(workspace_root: Path, files: list[str]) -> tuple[list[dict], list[str]]:
    """Validate each path; return (validation_results, list of valid paths to delete)."""
    valid_paths: list[str] = []
    results: list[dict] = []
    for f in files:
        if not isinstance(f, str):
            results.append({"path": str(f), "error": "Invalid path type"})
            continue
        target = workspace_root / f
        if not target.exists():
            results.append({"path": f, "error": f"File not found: {f}"})
            continue
        if not target.is_file():
            results.append({"path": f, "error": "Cannot delete directory, only files supported"})
            continue
        if not _ensure_in_workspace(workspace_root, target):
            results.append({"path": f, "error": "Path cannot escape workspace"})
            continue
        valid_paths.append(f)
    return results, valid_paths


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments") or params
    workspace_root = Path(params.get("workspace_root", ""))
    path = args.get("path", params.get("path", ""))
    files = args.get("files", params.get("files", []))
    max_workers = args.get("max_workers", params.get("max_workers"))
    decision_choice = args.get("_decision_choice", params.get("_decision_choice"))

    if not path and not files:
        print(json.dumps({"error": "path or files is required"}))
        return

    if path:
        files = [path] if isinstance(path, str) else ([path] if not isinstance(path, list) else path)
    if not isinstance(files, list):
        files = [files]

    validation_results, valid_paths = _validate_and_collect_files(workspace_root, files)
    if validation_results and not valid_paths:
        print(json.dumps({"success": False, "results": validation_results, "deleted": 0}))
        return

    # Phase 1: no confirmation yet — output __decision_request for frontend
    if not decision_choice:
        file_list = valid_paths
        msg_lines = [f"The following {len(file_list)} file(s) will be deleted:"] + [f"  · {p}" for p in file_list] + ["", "Confirm delete?"]
        out = {
            DECISION_REQUEST_KEY: {
                "message": "\n".join(msg_lines),
                "choices": [CONFIRM_CHOICE, CANCEL_CHOICE],
                "payload": {"files": file_list},
            },
        }
        print(json.dumps(out, ensure_ascii=False))
        return

    # Phase 2: user cancelled — _abort_run signals main agent to exit early
    if decision_choice == CANCEL_CHOICE:
        logger.info("[delete] phase2 user cancelled")
        print(json.dumps({
            "cancelled": True,
            "_abort_run": True,
            "message": "User cancelled the deletion",
            "results": [],
            "deleted": 0,
        }))
        return

    # Phase 2: user confirmed — perform delete
    logger.info("[delete] phase2 confirm deleting count=%d paths=%s", len(valid_paths), valid_paths)
    if len(valid_paths) > 1:
        workers = int(max_workers) if max_workers is not None else DELETE_PARALLEL_WORKERS
        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_delete_one, workspace_root, f): f for f in valid_paths}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"path": str(futures[fut]), "error": str(e)})
    else:
        results = [_delete_one(workspace_root, f) for f in valid_paths]

    all_success = all(r.get("success") for r in results)
    print(json.dumps({"success": all_success, "results": results, "deleted": sum(1 for r in results if r.get("success"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
