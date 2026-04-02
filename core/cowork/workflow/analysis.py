"""Shared workflow analysis helpers.

This module keeps batch detection, progress aggregation, and artifact checks
out of the main workflow engine so the engine can stay focused on orchestration.
"""

from __future__ import annotations

import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cowork.workflow.modes import StepStatus, WorkflowStatus
from core.cowork.workflow.state import StepState

_WORKFLOW_CONTEXT_JSON_MAX = 120_000
_BATCH_MIN_ITEMS = 2
_BATCH_PREVIEW_LIMIT = 5
_DEFAULT_BATCH_MODE = "per_item"
_FILE_OUTPUT_KEYWORDS = {
    "file",
    "artifact",
    "output",
    "export",
    "save",
    "write",
    "generate",
    "create",
    "produce",
    "download",
}
_BATCH_KEY_HINTS = {
    "urls",
    "url_list",
    "items",
    "rows",
    "records",
    "files",
    "input_files",
    "documents",
    "sources",
    "companies",
}
_BATCH_TEXT_HINTS = {
    "batch",
    "bulk",
    "each",
    "every",
    "all",
    "list",
    "sheet",
    "table",
    "rows",
    "records",
    "urls",
    "url column",
}
_FILE_ACTION_HINTS = {
    "write",
    "save",
    "export",
    "create",
    "generate",
    "produce",
    "output",
}


def looks_like_url(text: str) -> bool:
    return bool(re.match(r"^(https?://|www\.)", text, re.I) or re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", text, re.I))


def _build_batch_contract() -> dict[str, Any]:
    return {
        "mode": _DEFAULT_BATCH_MODE,
        "continue_on_error": True,
        "all_items_required": True,
    }


def _summarize_list(values: list[Any], source: str) -> dict[str, Any] | None:
    if not values:
        return None
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    if len(cleaned) < _BATCH_MIN_ITEMS:
        return None
    return {
        "batch_mode": True,
        "batch_kind": source,
        "batch_count": len(cleaned),
        "batch_preview": cleaned[:_BATCH_PREVIEW_LIMIT],
        "batch_contract": _build_batch_contract(),
    }


def _extract_batch_from_mapping(value: dict[str, Any]) -> dict[str, Any] | None:
    for key in _BATCH_KEY_HINTS:
        candidate = value.get(key)
        if isinstance(candidate, list):
            summary = _summarize_list(candidate, key)
            if summary:
                return summary
    for key, candidate in value.items():
        if isinstance(candidate, list):
            summary = _summarize_list(candidate, str(key))
            if summary:
                return summary
        if isinstance(candidate, dict):
            summary = extract_batch_summary(candidate)
            if summary:
                return summary
    return None


def _extract_batch_from_sequence(value: list[Any]) -> dict[str, Any] | None:
    summary = _summarize_list(value, "items")
    if summary:
        return summary
    for candidate in value:
        if isinstance(candidate, dict):
            summary = extract_batch_summary(candidate)
            if summary:
                return summary
    return None


def _extract_text_hint_batch_summary(obj: dict[str, Any]) -> dict[str, Any] | None:
    text_bits = []
    for key in ("goal", "question", "task", "description", "input", "prompt"):
        value = obj.get(key)
        if isinstance(value, str):
            text_bits.append(value)
    lowered = " ".join(text_bits).lower()
    if not any(hint in lowered for hint in _BATCH_TEXT_HINTS):
        return None
    return {
        "batch_mode": True,
        "batch_kind": "text_hint",
        "batch_count": 0,
        "batch_preview": [],
        "batch_contract": _build_batch_contract(),
    }


def extract_batch_summary(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        summary = _extract_batch_from_mapping(obj)
        if summary:
            return summary
        return _extract_text_hint_batch_summary(obj)
    if isinstance(obj, list):
        return _extract_batch_from_sequence(obj)
    return None


def coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except ValueError:
            return default
    return default


def _extract_nested_batch_progress(output: dict[str, Any]) -> dict[str, Any]:
    progress: dict[str, Any] = {}
    for key in ("batch_progress", "progress"):
        candidate = output.get(key)
        if isinstance(candidate, dict):
            progress.update(candidate)
    return progress


def _extract_flat_batch_progress(output: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    progress: dict[str, Any] = {}
    for key in ("total", "completed", "failed", "current_step_id", "current_item", "status"):
        if key in output and key not in current:
            progress[key] = output[key]
    return progress


def _progress_from_items(items: list[Any]) -> dict[str, Any]:
    return {
        "items": items,
        "total": len(items),
        "completed": len([item for item in items if isinstance(item, dict) and item.get("status") == "completed"]),
        "failed": len([item for item in items if isinstance(item, dict) and item.get("status") == "failed"]),
    }


def _progress_from_successes(successes: list[Any], current: dict[str, Any]) -> dict[str, Any]:
    progress: dict[str, Any] = {"successes": successes, "completed": len(successes)}
    if "total" not in current and "failed" in current:
        progress["total"] = progress["completed"] + coerce_int(current.get("failed"), 0)
    return progress


def _progress_from_failures(failures: list[Any], current: dict[str, Any]) -> dict[str, Any]:
    progress: dict[str, Any] = {"failures": failures}
    progress["failed"] = current.get("failed", len(failures))
    if "total" not in current and "completed" in current:
        progress["total"] = coerce_int(current.get("completed"), 0) + coerce_int(progress["failed"], 0)
    return progress


def _extract_sequence_batch_progress(output: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    progress: dict[str, Any] = {}
    items = output.get("items")
    if isinstance(items, list):
        progress.update(_progress_from_items(items))
    successes = output.get("successes")
    if isinstance(successes, list):
        progress.update(_progress_from_successes(successes, current))
    failures = output.get("failures") or output.get("errors")
    if isinstance(failures, list):
        progress.update(_progress_from_failures(failures, current))
    return progress


def extract_batch_progress_from_output(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {}
    progress: dict[str, Any] = {}
    progress.update(_extract_nested_batch_progress(output))
    progress.update(_extract_flat_batch_progress(output, progress))
    progress.update(_extract_sequence_batch_progress(output, progress))
    return progress


def _ordered_step_ids(steps: Dict[str, StepState]) -> List[str]:
    def sort_key(sid: str) -> tuple[int, str]:
        if sid.startswith("step_"):
            try:
                return (int(sid.split("_", 1)[1]), sid)
            except ValueError:
                pass
        return (10**9, sid)

    return sorted(steps.keys(), key=sort_key)


def build_batch_progress(
    input_data: Any,
    steps: Dict[str, StepState],
    current_step_id: Optional[str] = None,
    workflow_status: Optional[WorkflowStatus] = None,
) -> dict[str, Any]:
    summary = extract_batch_summary(input_data)
    if not summary:
        return {}

    progress: dict[str, Any] = {
        "batch_mode": True,
        "label": summary.get("batch_kind", "batch"),
        "total": summary.get("batch_count", 0),
        "completed": 0,
        "failed": 0,
        "current_item": summary.get("batch_preview", [None])[0] if summary.get("batch_preview") else None,
        "items_preview": summary.get("batch_preview", []),
        "batch_contract": summary.get("batch_contract"),
        "status": (workflow_status.value if isinstance(workflow_status, WorkflowStatus) else "queued"),
    }

    ordered_steps = _ordered_step_ids(steps)
    completed_steps = [steps[sid] for sid in ordered_steps if steps[sid].status == StepStatus.COMPLETED]
    failed_steps = [steps[sid] for sid in ordered_steps if steps[sid].status == StepStatus.FAILED]
    if completed_steps:
        latest = completed_steps[-1]
        output_progress = extract_batch_progress_from_output(latest.output_data)
        progress.update(output_progress)
    if "completed" not in progress:
        progress["completed"] = len(completed_steps)
    if "failed" not in progress:
        progress["failed"] = len(failed_steps)
    if workflow_status == WorkflowStatus.COMPLETED:
        progress["status"] = "completed"
    elif workflow_status == WorkflowStatus.FAILED:
        progress["status"] = "failed"
    elif workflow_status == WorkflowStatus.RUNNING:
        progress["status"] = "running"

    total = coerce_int(progress.get("total"), 0)
    completed = coerce_int(progress.get("completed"), 0)
    failed = coerce_int(progress.get("failed"), 0)
    if total <= 0 and (completed > 0 or failed > 0):
        progress["total"] = completed + failed

    if current_step_id and current_step_id in steps:
        current_step = steps[current_step_id]
        progress["current_step_id"] = current_step_id
        progress["current_step_name"] = current_step.name or current_step_id
        if current_step.status == StepStatus.RUNNING:
            progress["status"] = "running"
            if not progress.get("current_item"):
                progress["current_item"] = current_step.name or current_step_id
    return progress


def task_requests_file_output(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    action_hit = any(hint in lowered for hint in _FILE_ACTION_HINTS)
    output_hit = any(hint in lowered for hint in _FILE_OUTPUT_KEYWORDS)
    return action_hit and output_hit


def extract_output_paths(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        paths: list[str] = []
        for key in ("output_file", "output_files", "file", "file_path", "path"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
            elif isinstance(value, list):
                paths.extend(str(item).strip() for item in value if str(item).strip())
        return paths
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    if isinstance(payload, str):
        return [payload.strip()] if payload.strip() else []
    return []


def count_csv_data_rows(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
    except Exception:
        return None
    if not rows:
        return 0
    data_rows = rows[1:] if len(rows) > 1 else []
    return len([row for row in data_rows if any(cell.strip() for cell in row)])


def scan_recent_files(
    workspace_root: Path,
    since: datetime,
) -> list[Path]:
    if not workspace_root.exists():
        return []
    candidates: list[Path] = []
    for path in workspace_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime >= since:
            candidates.append(path)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates
