"""
Retrieval strategy: fetch content for keys via search or crawler.

When key looks like a URL and retrieve_mode is crawl or auto, uses crawler.scrape
for full page content. Otherwise uses search skill for snippets.
Used by fill_by_column in batches; one key -> one content string.
"""

import asyncio
import logging
from typing import Any

from _config import (
    DEPENDENCY_SKILL_CRAWLER,
    DEPENDENCY_SKILL_SEARCH,
    RETRIEVE_MODE_AUTO,
    RETRIEVE_MODE_CRAWL,
    RETRIEVE_MODE_SEARCH,
)

logger = logging.getLogger(__name__)

_COMMON_TLDS = frozenset(("com", "org", "net", "io", "co", "edu", "gov", "info", "biz"))


def _is_like_url(key: str) -> bool:
    """Return True if key appears to be a URL or domain."""
    s = (key or "").strip()
    if not s or len(s) > 256:
        return False
    if s.startswith("http://") or s.startswith("https://"):
        return True
    if " " in s:
        return False
    if "." not in s:
        return False
    parts = s.lower().split(".")
    if len(parts) < 2:
        return False
    tld = parts[-1]
    return tld in _COMMON_TLDS or len(tld) == 2


def _normalize_url(key: str) -> str:
    """Ensure key has a scheme for crawler. Returns key with https:// if missing."""
    s = (key or "").strip()
    if not s:
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://{s}"


async def _retrieve_via_crawl(
    key: str,
    execute_skill_fn: Any,
    ctx: dict,
    project_root: Any,
) -> str:
    """Fetch full page content via crawler.scrape. Returns content string."""
    url = _normalize_url(key)
    db_path = ctx.get("db_path")
    if db_path is not None and hasattr(db_path, "exists") and not db_path.exists():
        db_path = None
    try:
        result = await execute_skill_fn(
            skill_name=DEPENDENCY_SKILL_CRAWLER,
            action="scrape",
            arguments={"url": url, "wait_for": 2000},
            workspace_root=ctx["workspace_root"],
            session_id=ctx["session_id"],
            user_id=ctx["user_id"],
            root=project_root,
            db_path=db_path,
            call_stack=ctx.get("call_stack", []),
        )
    except Exception as e:
        logger.warning("[excel-ops._retrieve] crawl key=%s error=%s", key[:80], e)
        return ""
    if result.get("error"):
        logger.warning("[excel-ops._retrieve] crawl key=%s skill_error=%s", key[:80], result["error"])
        return ""
    return str(result.get("result") or "")


async def _retrieve_via_search(
    key: str,
    execute_skill_fn: Any,
    ctx: dict,
    project_root: Any,
    search_num: int,
) -> str:
    """Fetch content via search skill. Returns snippets string."""
    db_path = ctx.get("db_path")
    if db_path is not None and hasattr(db_path, "exists") and not db_path.exists():
        db_path = None
    try:
        result = await execute_skill_fn(
            skill_name=DEPENDENCY_SKILL_SEARCH,
            action="search",
            arguments={"query": key.strip(), "num": search_num},
            workspace_root=ctx["workspace_root"],
            session_id=ctx["session_id"],
            user_id=ctx["user_id"],
            root=project_root,
            db_path=db_path,
            call_stack=ctx.get("call_stack", []),
        )
    except Exception as e:
        logger.warning("[excel-ops._retrieve] search key=%s error=%s", key[:80], e)
        return ""
    if result.get("error"):
        logger.warning("[excel-ops._retrieve] search key=%s skill_error=%s", key[:80], result["error"])
        return ""
    return str(result.get("result") or "")


async def retrieve_one(
    key: str,
    execute_skill_fn: Any,
    ctx: dict,
    project_root: Any,
    search_num: int = 5,
    retrieve_mode: str = RETRIEVE_MODE_AUTO,
) -> str:
    """Fetch content for a single key. Returns content string."""
    if not key or not key.strip():
        return ""
    query = key.strip()
    use_crawl = False
    if retrieve_mode == RETRIEVE_MODE_CRAWL:
        use_crawl = True
    elif retrieve_mode == RETRIEVE_MODE_SEARCH:
        use_crawl = False
    else:
        use_crawl = _is_like_url(query)
    if use_crawl:
        return await _retrieve_via_crawl(query, execute_skill_fn, ctx, project_root)
    return await _retrieve_via_search(query, execute_skill_fn, ctx, project_root, search_num)


async def retrieve_batch(
    keys: list[str],
    execute_skill_fn: Any,
    ctx: dict,
    project_root: Any,
    search_num: int = 5,
    retrieve_mode: str = RETRIEVE_MODE_AUTO,
) -> dict[str, str]:
    """Fetch content for multiple keys in parallel. Returns mapping key -> content."""
    if not keys:
        return {}
    tasks = [
        retrieve_one(k, execute_skill_fn, ctx, project_root, search_num, retrieve_mode)
        for k in keys
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, str] = {}
    for k, r in zip(keys, results):
        if isinstance(r, Exception):
            logger.warning("[excel-ops._retrieve] key=%s exception=%s", k[:80], r)
            out[k] = ""
        else:
            out[k] = str(r) if r else ""
    return out
