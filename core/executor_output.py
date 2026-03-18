"""
Skill Executor - Output processing and validation.

Validates skill output against schemas and logs to DB.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from constants import EXECUTOR_RESULT_PREVIEW_LEN, EXECUTOR_TRACE_PREVIEW_LEN

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillRunContext:
    """Context for process step: logging and output validation.

    Attributes:
        skill_dir: Skill directory path.
        resolved_action: Resolved action name.
        skill_name: Skill name.
        db_path: Optional SQLite DB path for traces/logs.
        session_id: Session ID.
    """

    skill_dir: Path
    resolved_action: str
    skill_name: str
    db_path: Path | None
    session_id: str


def validate_output_contract(
    skill_dir: Path,
    action: str,
    result: dict[str, Any],
) -> bool:
    """Validate result against output schema if present.

    Args:
        skill_dir: Skill directory (schemas live under schemas/).
        action: Action name (schema file is {action}_output.json).
        result: Parsed result dict to validate.

    Returns:
        True if valid or no schema file exists; False on validation failure
        (caller may strip gen_ui etc.).
    """
    schema_path = skill_dir / "schemas" / f"{action}_output.json"
    if not schema_path.exists():
        return True
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=result, schema=schema)
        return True
    except Exception as e:
        logger.warning(
            "[executor] output_contract_validation_failed skill=%s action=%s error=%s",
            skill_dir.name,
            action,
            e,
        )
        return False


def log_skill_error(
    db_path: Path | None,
    session_id: str,
    skill_name: str,
    action: str,
    err_msg: str,
) -> None:
    """Log skill error to DB when db_path is provided and exists."""
    if db_path and db_path.exists():
        from db.logs import insert as log_insert
        log_insert(
            db_path,
            "ERROR",
            f"skill_error {skill_name}.{action}: {err_msg}",
            session_id,
            {"error": err_msg},
        )


def log_skill_success(
    db_path: Path | None,
    session_id: str,
    skill_name: str,
    action: str,
    result: dict,
    latency_ms: int,
) -> None:
    """Write trace and metrics to DB when db_path is provided and exists."""
    if not db_path or not db_path.exists():
        return
    from db.traces import insert as trace_insert
    from db.logs import insert as log_insert
    from db.metrics import insert as metrics_insert
    preview = json.dumps(result, ensure_ascii=False)[:EXECUTOR_TRACE_PREVIEW_LEN]
    trace_insert(db_path, session_id, skill_name, action, 0, preview, {"latency_ms": latency_ms})
    metrics_insert(
        db_path,
        "skill_latency_ms",
        float(latency_ms),
        tags={"skill": skill_name, "action": action, "session_id": session_id},
    )
    if result.get("error"):
        log_insert(
            db_path,
            "ERROR",
            f"skill_error {skill_name}.{action}: {result.get('error', '')}",
            session_id,
            {"error": str(result.get("error"))},
        )
    else:
        log_insert(
            db_path,
            "INFO",
            f"skill_execute {skill_name}.{action}",
            session_id,
            {"latency_ms": latency_ms},
        )


def process_skill_output(
    ctx: SkillRunContext,
    raw_output: str,
    script_path: Path,
    start: float,
) -> dict[str, Any]:
    """Parse script output, validate contract, log success; return result or error dict.

    Handles empty output, invalid JSON, and schema validation. On success
    computes latency, logs to DB, and returns the result dict.

    Args:
        ctx: Skill run context.
        raw_output: Raw stdout string from the skill script.
        script_path: Path to the script (for log messages).
        start: Monotonic start time from before run_script.

    Returns:
        Result dict from the skill (or {"error": "..."} on parse/validation failure).
    """
    out_stripped = (raw_output or "").strip()
    if not out_stripped:
        err_msg = "Skill script returned empty output"
        logger.warning(
            "[executor] skill=%s action=%s empty_output script=%s",
            ctx.skill_name, ctx.resolved_action, script_path,
        )
        log_skill_error(
            ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, err_msg
        )
        return {"error": err_msg}

    try:
        result = json.loads(out_stripped)
    except json.JSONDecodeError as e:
        err_msg = f"Invalid skill output: {e}"
        logger.warning(
            "[executor] skill=%s action=%s json_error script=%s preview=%r",
            ctx.skill_name, ctx.resolved_action, script_path,
            out_stripped[:EXECUTOR_RESULT_PREVIEW_LEN],
        )
        log_skill_error(
            ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, err_msg
        )
        return {"error": err_msg}

    if not validate_output_contract(ctx.skill_dir, ctx.resolved_action, result):
        result = {k: v for k, v in result.items() if k != "gen_ui"}

    latency_ms = int((time.time() - start) * 1000)
    logger.info(
        "[executor] skill=%s action=%s ok latency_ms=%d",
        ctx.skill_name, ctx.resolved_action, latency_ms,
    )
    log_skill_success(
        ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, result, latency_ms
    )
    return result
