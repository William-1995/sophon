#!/usr/bin/env python3
"""
Sophon V7 - CLI Entry Point.

Usage: python main.py [question]
       python main.py   # default: "What can you help with?"

CLI does not support /skill or @file - tests LLM understanding.
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import bootstrap, get_config, DEFAULT_USER_ID, SESSION_ID_LENGTH
from core.providers import get_provider
from core.react import run_react
from db.schema import ensure_db_ready

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    bootstrap()
    cfg = get_config()
    db_path = cfg.paths.db_path()
    ensure_db_ready(db_path)

    question = sys.argv[1] if len(sys.argv) > 1 else "What can you help with?"
    session_id = f"cli-{uuid.uuid4().hex[:SESSION_ID_LENGTH]}"
    workspace_root = cfg.paths.user_workspace()

    provider = get_provider("deepseek")
    answer, meta = await run_react(
        question=question,
        provider=provider,
        workspace_root=workspace_root,
        session_id=session_id,
        user_id=DEFAULT_USER_ID,
        skill_filter=None,
        db_path=db_path,
    )
    if db_path.exists():
        from db.memory_long_term import insert as memory_insert
        memory_insert(db_path, session_id, "user", question)
        memory_insert(db_path, session_id, "assistant", answer)
    print(answer)
    if meta.get("tokens"):
        logger.info("Tokens used: %s", meta["tokens"])


if __name__ == "__main__":
    asyncio.run(main())
