"""Investigation helpers for task_plan.

Keep file discovery, PDF sizing, and thinking-trace emission separate from the
planner runner so the orchestrator stays readable.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any

from core.ipc import emit_event

_TOKEN_PATTERN = re.compile(r"[a-z0-9_+-]+", re.IGNORECASE)
_PATH_SIGNAL_PATTERN = re.compile(r"(@\S+|\.[a-z0-9]{2,6}\b|[\\/])", re.IGNORECASE)
_FILE_INTENT_PATTERN = re.compile(
    r"(?i)\b(read|open|parse|extract|summarize|analyze|convert|transform|inspect)\b"
)
_EXPLICIT_REF_PATTERN = re.compile(r"@([^\s]+)")
_FILENAME_PATTERN = re.compile(r"([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]{2,6})")
_TOOL_FILE_HINTS = ("file", "read", "parse", "extract", "filesystem")

_BATCH_TEXT_HINTS = (
    "batch",
    "bulk",
    "each",
    "every",
    "all",
    "list",
    "table",
    "rows",
    "records",
    "urls",
    "url column",
)



def _detect_batch_signal(question: str) -> dict[str, Any] | None:
    q = (question or "").lower()
    hits = [hint for hint in _BATCH_TEXT_HINTS if hint in q]
    if not hits:
        return None
    return {
        "batch_mode": True,
        "batch_keywords": hits,
        "batch_contract": (
            "Treat the request as a batch workflow. Keep the whole collection in scope "
            "and avoid collapsing it into a single sample item."
        ),
    }



def emit_task_plan_event(event_sink: Any | None, event: dict[str, Any]) -> None:
    if callable(event_sink):
        try:
            event_sink(event)
            return
        except Exception:
            pass
    emit_event(event)



def emit_thinking_trace(
    event_sink: Any | None,
    question: str,
    tools_brief: list[dict[str, str]] | None,
    missing_inputs: list[str],
    candidate_files: list[str],
    *,
    ready_for_planning: bool,
    file_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_names = [
        str(tool.get("name", "")).strip()
        for tool in (tools_brief or [])
        if str(tool.get("name", "")).strip()
    ]
    investigation = {
        "intent": question,
        "inputs_found": list(candidate_files),
        "inputs_missing": list(missing_inputs),
        "candidate_files": list(candidate_files),
        "usable_tools": tool_names,
        "blocked_reasons": list(missing_inputs),
        "ready_for_planning": ready_for_planning,
        "recommended_next_action": "plan" if ready_for_planning else "clarify",
    }
    batch_signal = _detect_batch_signal(question)
    if batch_signal:
        investigation.update(batch_signal)
    if file_structure:
        investigation["file_structure"] = file_structure
    trace_parts = [f"Thinking about the request: {question}"]
    if tool_names:
        trace_parts.append("Available tools: " + ", ".join(tool_names))
    if batch_signal:
        trace_parts.append("Batch mode detected; keep every item in scope and avoid sampling the first item.")
    if missing_inputs:
        trace_parts.append("Missing inputs: " + ", ".join(missing_inputs))
    else:
        trace_parts.append(
            "No obvious missing inputs; preparing a plan-ready investigation summary."
        )
    trace_parts.append(f"Next action: {investigation['recommended_next_action']}")
    for part in trace_parts:
        emit_task_plan_event(event_sink, {"type": "THINKING", "content": part, "payload": dict(investigation)})
    emit_task_plan_event(event_sink, {"type": "INVESTIGATION_REPORT", "payload": investigation})
    return investigation


def _tokenize(value: str) -> set[str]:
    return {t.lower() for t in _TOKEN_PATTERN.findall(value or "") if len(t) >= 3}


def _tool_tokens(tools_brief: list[dict[str, str]] | None) -> set[str]:
    tokens: set[str] = set()
    for tool in tools_brief or []:
        if not isinstance(tool, dict):
            continue
        tokens.update(_tokenize(str(tool.get("name", ""))))
        tokens.update(_tokenize(str(tool.get("description", ""))))
    return tokens


def extract_query_terms(question: str) -> list[str]:
    return sorted(_tokenize(question))


def _resolve_reference(root: Path, raw_ref: str) -> str | None:
    ref = str(raw_ref or "").strip()
    if not ref:
        return None
    while ref.startswith("@"):  # allow @@path style accidental input
        ref = ref[1:].lstrip("/")
    candidate = (root / ref).resolve()
    try:
        rel = candidate.relative_to(root.resolve())
    except Exception:
        return None
    if candidate.exists() and candidate.is_file():
        return rel.as_posix()
    return None


def _explicit_file_refs(question: str, root: Path) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for match in _EXPLICIT_REF_PATTERN.findall(question or ""):
        resolved = _resolve_reference(root, match)
        if resolved and resolved not in seen:
            refs.append(resolved)
            seen.add(resolved)
    return refs


def _mentioned_filenames(question: str, root: Path) -> list[str]:
    names = {m.lower() for m in _FILENAME_PATTERN.findall(question or "")}
    if not names:
        return []
    matches: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() in names:
            matches.append(path.relative_to(root).as_posix())
        if len(matches) >= 12:
            break
    return matches



def discover_candidate_files(
    question: str,
    workspace_root: str | Path | None,
) -> list[str]:
    if not workspace_root:
        return []
    root = Path(workspace_root)
    if not root.exists() or not root.is_dir():
        return []

    explicit = _explicit_file_refs(question, root)
    if explicit:
        return explicit

    return _mentioned_filenames(question, root)



def page_range_chunks(total_pages: int, chunk_size: int = 500) -> list[str] | None:
    if total_pages <= chunk_size:
        return None
    ranges: list[str] = []
    start = 1
    while start <= total_pages:
        end = min(start + chunk_size - 1, total_pages)
        ranges.append(f"{start}-{end}")
        start = end + 1
    return ranges



def inspect_pdf_structure(pdf_path: Path) -> dict[str, Any] | None:
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    try:
        with pdf_path.open("rb") as fh:
            reader = PdfReader(BytesIO(fh.read()))
        total_pages = len(reader.pages)
        structure: dict[str, Any] = {
            "pages": total_pages,
            "recommended_chunk_size": 500,
        }
        suggested = page_range_chunks(total_pages, 500)
        if suggested:
            structure["suggested_page_ranges"] = suggested
        try:
            outline = []
            raw_outline = reader.outline
            if raw_outline:
                for item in raw_outline:
                    if isinstance(item, list):
                        continue
                    try:
                        title = getattr(item, "title", None) or (item.get("/Title", "") if hasattr(item, "get") else "")
                        page_num = reader.get_destination_page_number(item)
                        if page_num is not None:
                            page_num += 1
                        outline.append({"title": str(title), "page": page_num})
                    except Exception:
                        pass
            if outline:
                structure["outline"] = outline
        except Exception:
            pass
        return structure
    except Exception:
        return None



def _tools_can_handle_files(tools_brief: list[dict[str, str]] | None) -> bool:
    tokens = _tool_tokens(tools_brief)
    return any(hint in tokens for hint in _TOOL_FILE_HINTS)



def looks_like_missing_file_input(question: str, tools_brief: list[dict[str, str]] | None) -> list[str]:
    q = (question or "").strip()
    if not q:
        return []
    if _PATH_SIGNAL_PATTERN.search(q):
        return []
    if not _tools_can_handle_files(tools_brief):
        return []
    if not _FILE_INTENT_PATTERN.search(q.lower()):
        return []
    return ["file path"]
