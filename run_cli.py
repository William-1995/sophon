#!/usr/bin/env python3
"""Sophon CLI: one-shot question to the ReAct agent (no /skill or @file).

Usage: python run_cli.py [question]
       python run_cli.py   # default: "What can you help with?"
"""

import asyncio
import logging
import sys
import uuid

import bootstrap_paths
from config import DEFAULT_USER_ID, SESSION_ID_LENGTH, bootstrap, get_config
from core.react import run_react
from db.schema import configure_default_database, ensure_db_ready
from providers import get_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bootstrap_paths.activate()


async def main() -> None:
    """Run one-shot CLI query to the ReAct agent.

    Bootstraps the application, initializes database, and runs the agent loop
    with the provided question. Stores conversation in memory if database exists.
    """
    bootstrap()
    cfg = get_config()
    db_path = cfg.paths.db_path()
    ensure_db_ready(db_path)
    configure_default_database(db_path)

    question = (
        sys.argv[1] if len(sys.argv) > 1 else "What can you help with?"
    )
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
