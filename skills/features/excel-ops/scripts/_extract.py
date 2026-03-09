"""
LLM batch extraction: given a list of (key, content), return a list of dicts (one per row)
with target_columns filled. Used by fill_by_column after retrieve_batch.
"""

import json
import logging
import re
from typing import Any

from _config import CONTENT_PREVIEW_LEN, DEFAULT_EXTRACT_INSTRUCTIONS

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """Extract JSON from markdown code fences or raw text."""
    s = (text or "").strip()
    if "```" in s:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if m:
            return m.group(1).strip()
        first = s.find("```")
        rest = s[first + 3 :]
        if "```" in rest:
            return rest.split("```", 1)[0].strip()
    return s


async def extract_batch(
    items: list[tuple[str, str]],
    target_columns: list[str],
    instructions: str,
    provider: Any,
    content_preview_len: int = CONTENT_PREVIEW_LEN,
) -> list[dict[str, Any]]:
    """
    Run one LLM call for the batch. items = [(key, content), ...].
    Returns list of dicts, one per item, each dict mapping target_columns to values.
    """
    if not items or not target_columns:
        return []

    batch_parts = []
    for i, (key, content) in enumerate(items):
        preview = (content or "")[:content_preview_len]
        batch_parts.append(
            f"Row {i + 1} (key={key!r}):\n{preview}"
        )

    system_prompt = (
        "You are an assistant that fills workbook columns from web search snippets. "
        "Return ONLY a JSON array of objects. One object per row in the same order. "
        "Each object should have a key for each target column; use empty string when absent or uncertain. "
        "Fill every target column when the content allows. No commentary, only the JSON array."
    )
    default_instructions = DEFAULT_EXTRACT_INSTRUCTIONS
    user_prompt = (
        f"Target columns: {target_columns}\n"
        f"Instructions: {instructions or default_instructions}\n\n"
        "Batch (rows in order):\n"
        + "\n---\n".join(batch_parts)
        + "\n\n"
        "Respond ONLY with a JSON array of objects, one per row, each object mapping target column names to values. "
        "Example: [{\"col1\": \"val1\", \"col2\": \"\"}, ...]"
    )

    try:
        resp = await provider.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as e:
        logger.warning("[excel-ops._extract] provider.chat error=%s", e)
        return []

    content = resp.get("content") or ""
    text = _extract_json(content)
    try:
        arr = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("[excel-ops._extract] json_decode_error=%s preview=%s", e, text[:200])
        return []

    if not isinstance(arr, list):
        logger.warning("[excel-ops._extract] output_not_array type=%s", type(arr))
        return []

    result: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        mapping = arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
        result.append(mapping)
    logger.info("[excel-ops._extract] batch_size=%d parsed=%d", len(items), len(result))
    return result
