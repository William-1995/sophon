"""Lightweight, capability-agnostic question heuristics for ReAct."""

import re

_GENERIC_TOOL_SIGNAL_PATTERN = re.compile(
    r"(?i)("
    r"@\S+|"  # explicit file refs
    r"https?://|www\\.|"  # web refs
    r"[a-z0-9_.-]+\.[a-z0-9]{2,8}\b|"  # generic filename.ext
    r"[/\\]"  # path separators
    r")",
    re.UNICODE,
)

_MULTI_PART_CONNECTOR_PATTERN = re.compile(r"(?i)(and|then|also|同时|以及|并且|and/or)")
_MULTI_PART_SEPARATOR_PATTERN = re.compile(r"[，,;；]\s*")
_EXPLICIT_REF_PATTERN = re.compile(r"@\S+")


def question_suggests_tool_execution(question: str) -> bool:
    """True when the user text likely implies concrete tool use."""
    q = (question or "").strip()
    if len(q) < 4:
        return False
    return bool(_GENERIC_TOOL_SIGNAL_PATTERN.search(q))



def question_suggests_multi_part(question: str) -> bool:
    """Heuristic for requests that likely include multiple tasks or items."""
    q = (question or "").strip()
    if len(q) < 25:
        return False
    if _MULTI_PART_CONNECTOR_PATTERN.search(q):
        return True
    if _MULTI_PART_SEPARATOR_PATTERN.search(q):
        return True
    if len(_EXPLICIT_REF_PATTERN.findall(q)) >= 2:
        return True
    return False
