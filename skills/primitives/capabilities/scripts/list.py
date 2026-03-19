#!/usr/bin/env python3
"""Return Sophon intro and skill names only. LLM summarizes for the user."""
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _format_section_title(tier: str, channel: str) -> str:
    if tier == "optional":
        return "" if channel == "entertainment" else (channel or "optional")
    return f"{tier} / {channel}" if channel else tier


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    params = json.loads(sys.stdin.read() or "{}")
    session_id = params.get("_executor_session_id")
    db_path = Path(params["db_path"]) if params.get("db_path") else None

    try:
        from config import get_config
        from core.skill_loader import get_skills_brief_grouped
        from db.logs import insert as log_insert

        if db_path is None:
            db_path = get_config().paths.db_path()

        grouped = get_skills_brief_grouped()
        section_lines: list[str] = []
        total_skills = 0

        for group in grouped:
            skills = group.get("skills", [])
            tier = group.get("tier", "")
            channel = group.get("channel", "")
            if tier == "optional" and channel == "entertainment":
                skills = [s for s in skills if s["skill_name"] == "emotion-awareness"]
            if not skills:
                continue
            title = _format_section_title(tier, channel)
            skill_lines = [f"- {s['skill_name']}" for s in skills]
            if title:
                section_lines.append(f"### {title}\n\n" + "\n".join(skill_lines))
            else:
                section_lines.append("\n".join(skill_lines))
            total_skills += len(skills)

        intro = "I am Sophon, a skill-native AI agent."

        if section_lines:
            text = (
                intro
                + "\n\nAvailable skills:\n\n"
                + "\n\n".join(section_lines)
            )
        else:
            text = intro + "\n\nNo skills are currently configured."

        if db_path and db_path.exists():
            log_insert(db_path, "INFO", "capabilities.list", session_id, {"skills_count": total_skills})
        logger.info("capabilities.list ok (skills_count=%d)", total_skills)

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
