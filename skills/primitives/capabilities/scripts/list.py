#!/usr/bin/env python3
"""Return Sophon introduction and exposed skills (name + description)."""
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    params = json.loads(sys.stdin.read() or "{}")
    session_id = params.get("_executor_session_id")
    db_path = Path(params["db_path"]) if params.get("db_path") else None

    try:
        from config import get_config
        from core.skill_loader import get_skills_brief
        from db.logs import insert as log_insert

        if db_path is None:
            db_path = get_config().paths.db_path()

        brief = get_skills_brief()
        capability_lines = [f"- **{s['skill_name']}**: {s['skill_description']}" for s in brief]

        intro_lines = [
            "I am Sophon, a local, skill-native AI agent that orchestrates tools defined as skills.",
            "I run on your machine and store logs, traces, metrics, and memory locally.",
        ]

        if capability_lines:
            text = (
                "\n".join(intro_lines)
                + "\n\nAvailable capabilities:\n\n"
                + "\n".join(capability_lines)
            )
        else:
            text = "\n".join(intro_lines) + "\n\nNo capabilities are currently configured."

        if db_path and db_path.exists():
            log_insert(db_path, "INFO", "capabilities.list", session_id, {"skills_count": len(brief)})
        logger.info("capabilities.list ok (skills_count=%d)", len(brief))

        print(json.dumps({"result": text, "observation": text, "answer": text}))
    except Exception as e:
        logger.exception("capabilities.list failed")
        try:
            if db_path and db_path.exists():
                from db.logs import insert as log_insert
                log_insert(db_path, "ERROR", f"capabilities.list error: {e}", session_id, {"error": str(e)})
        except Exception:
            pass
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
