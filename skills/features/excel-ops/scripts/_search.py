"""
Excel-Ops Enrich - Search operations.

Provides search query building and execution for enrichment.
"""

import re
from typing import Any


def build_search_query(row_values: dict[str, Any], id_column: str, company_column: str | None) -> str:
    """Build search query from row values.

    Args:
        row_values: Dict of column name to cell value.
        id_column: Name of the ID column.
        company_column: Optional name of company column to combine with ID.

    Returns:
        Search query string. Empty string if id_column value is empty.
    """
    id_val = str(row_values.get(id_column) or "").strip()
    if not id_val:
        return ""

    if company_column:
        company_val = str(row_values.get(company_column) or "").strip()
        if company_val:
            return f"{company_val} {id_val}"

    return id_val


def extract_json(text: str) -> str:
    """Extract JSON from markdown code fences or raw text.

    Args:
        text: Text that may contain JSON in code fences.

    Returns:
        Extracted JSON string or original text if no code fences.
    """
    s = str(text).strip()

    if "```" in s:
        # Try to find JSON in code fences
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if m:
            return m.group(1).strip()

        # Fallback: take content between first ``` and next ```
        first = s.find("```")
        rest = s[first + 3 :]
        if "```" in rest:
            inner = rest.split("```", 1)[0]
            return inner.strip()

    return s
