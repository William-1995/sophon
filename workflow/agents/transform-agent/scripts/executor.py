"""Cowork transform agent: convert tabular and document formats via skill subprocesses."""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Dict, List

from config import get_config

from core.cowork.agent_base import AgentContext
from core.cowork.runtime.runtime import AgentResult, AgentExecutor
from core.execution.bridge import execute_skill

SkillRunner = Callable[[str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


class TransformExecutor(AgentExecutor):
    """Orchestrates ``execute_skill`` calls for spreadsheet/PDF/Word/Markdown pipelines.

    Attributes:
        SUPPORTED_FORMATS (list[str]): Input/output format names accepted by routing.
        OUTPUT_SUFFIXES (dict[str, str]): Default file extensions per format.
    """

    SUPPORTED_FORMATS = ["csv", "json", "pdf", "markdown", "txt", "docx"]
    OUTPUT_SUFFIXES = {
        "csv": ".csv",
        "json": ".json",
        "pdf": ".pdf",
        "markdown": ".md",
        "txt": ".txt",
        "docx": ".docx",
    }

    async def execute(
        self,
        context: AgentContext,
        task: Dict[str, Any],
    ) -> AgentResult:
        """Route ``input_files`` to parse/convert skills for ``output_format``.

        Args:
            context (AgentContext): Provides workspace, user, and session for nested skills.
            task (dict[str, Any]): ``input_file`` / ``input_files``, ``output_format``, optional ``output_path``.

        Returns:
            AgentResult: Paths or content from the transform pipeline, or errors.
        """
        input_files = self._normalize_input_files(task)
        output_format = task.get("output_format") or task.get("target_format")
        output_path = task.get("output_path")
        workspace_root = str(context.global_context.get("workspace_root") or get_config().paths.user_workspace())
        user_id = str(context.global_context.get("user_id") or "default_user")

        async def run_skill(skill_name: str, action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return await execute_skill(
                skill_name=skill_name,
                action=action,
                arguments=arguments,
                workspace_root=workspace_root,
                session_id=context.session_id,
                user_id=user_id,
            )

        if not input_files:
            return AgentResult(success=False, error_message="No input file provided")

        if not output_format:
            return AgentResult(success=False, error_message="No output format specified")

        if output_format.lower() not in self.SUPPORTED_FORMATS:
            return AgentResult(
                success=False,
                error_message=(
                    f"Unsupported format: {output_format}. "
                    f"Supported: {', '.join(self.SUPPORTED_FORMATS)}"
                ),
            )

        try:
            if len(input_files) == 1:
                input_file = input_files[0]
                input_format = self._detect_format(input_file)
                return await self._convert_one(run_skill, input_file, input_format, output_format, output_path, workspace_root)
            return await self._convert_many(run_skill, input_files, output_format, output_path, workspace_root)
        except Exception as e:  # noqa: BLE001
            return AgentResult(success=False, error_message=f"Transformation failed: {str(e)}")

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "csv_conversion",
            "pdf_conversion",
            "markdown_conversion",
            "docx_conversion",
            "json_processing",
            "text_processing",
        ]

    def _normalize_input_files(self, task: Dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for key in ("input_files", "files"):
            value = task.get(key)
            candidates.extend(self._flatten_file_values(value))
        for key in ("input_file", "file_path"):
            value = task.get(key)
            if value:
                candidates.extend(self._flatten_file_values(value))

        normalized: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if not item:
                continue
            resolved = str(item).strip()
            if not resolved or resolved in seen:
                continue
            seen.add(resolved)
            normalized.append(resolved)
        return normalized

    def _flatten_file_values(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            flattened: list[str] = []
            for item in value:
                flattened.extend(self._flatten_file_values(item))
            return flattened
        if isinstance(value, dict):
            for key in ("file_path", "input_file", "path", "file"):
                nested = value.get(key)
                if nested:
                    return [str(nested)]
            return []
        return [str(value)]

    def _detect_format(self, file_path: str) -> str:
        """Detect file format from extension."""
        ext = os.path.splitext(file_path)[1].lower()
        format_map = {
            ".csv": "csv",
            ".json": "json",
            ".pdf": "pdf",
            ".md": "markdown",
            ".markdown": "markdown",
            ".txt": "txt",
            ".docx": "docx",
            ".doc": "docx",
        }
        return format_map.get(ext, "unknown")

    def _target_suffix(self, output_format: str) -> str:
        return self.OUTPUT_SUFFIXES.get(output_format.lower(), f".{output_format.lower()}")

    def _normalize_output_path(self, output_path: str | None, workspace_root: str) -> str | None:
        if not output_path:
            return None
        candidate = Path(str(output_path))
        if candidate.is_absolute():
            try:
                return str(candidate.resolve().relative_to(Path(workspace_root).resolve()))
            except ValueError:
                return str(candidate.resolve())
        normalized = candidate.as_posix().lstrip('./')
        if not normalized:
            return None
        return normalized

    def _derive_output_path(
        self,
        input_file: str,
        output_format: str,
        output_path: str | None,
        index: int = 0,
        total: int = 1,
    ) -> str:
        input_path = Path(input_file)
        suffix = self._target_suffix(output_format)

        if output_path:
            base = Path(output_path)
            if total > 1 and base.suffix:
                base = base.parent / base.stem
            if total == 1:
                if base.suffix:
                    return str(base)
                if base.exists() and base.is_dir():
                    return str(base / f"{input_path.stem}{suffix}")
                return str(base)
            base_dir = base if not base.suffix else base.parent / base.stem
        else:
            base_dir = input_path.parent

        base_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{index + 1:02d}_" if total > 1 else ""
        name = input_path.stem or f"input_{index + 1:02d}"
        return str(base_dir / f"{prefix}{name}{suffix}")

    async def _convert_many(
        self,
        run_skill: SkillRunner,
        input_files: list[str],
        output_format: str,
        output_path: str | None,
        workspace_root: str,
    ) -> AgentResult:
        total = len(input_files)
        items: list[dict[str, Any]] = []
        failures: list[str] = []

        for index, input_file in enumerate(input_files):
            per_output_path = self._derive_output_path(input_file, output_format, output_path, index, total)
            input_format = self._detect_format(input_file)
            result = await self._convert_one(run_skill, input_file, input_format, output_format, per_output_path, workspace_root)
            item = {
                "input_file": input_file,
                "output_file": result.output.get("output_file") or per_output_path,
                "format": result.output.get("format") or output_format,
                "preview": result.output.get("preview"),
                "success": result.success,
            }
            if result.error_message:
                item["error_message"] = result.error_message
                failures.append(f"{Path(input_file).name}: {result.error_message}")
            items.append(item)

        success = not failures
        output = {
            "batch": True,
            "input_files": input_files,
            "output_files": [item["output_file"] for item in items if item.get("output_file")],
            "results": items,
            "format": output_format,
            "succeeded_count": sum(1 for item in items if item.get("success")),
            "failed_count": sum(1 for item in items if not item.get("success")),
        }
        return AgentResult(
            success=success,
            output=output,
            error_message="; ".join(failures) if failures else None,
        )

    async def _convert_one(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_format: str,
        output_path: str | None,
        workspace_root: str,
    ) -> AgentResult:
        if output_format == "pdf":
            return await self._to_pdf(run_skill, input_file, input_format, output_path)
        if output_format == "markdown":
            return await self._to_markdown(run_skill, input_file, input_format, output_path)
        if output_format == "csv":
            return await self._to_csv(run_skill, input_file, input_format, output_path, workspace_root)
        if output_format == "docx":
            return await self._to_docx(run_skill, input_file, input_format, output_path)
        if output_format == "txt":
            return await self._to_txt(run_skill, input_file, input_format, output_path)
        return AgentResult(
            success=False,
            error_message=f"Conversion from {input_format} to {output_format} not supported",
        )

    async def _to_pdf(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_path: str | None,
    ) -> AgentResult:
        """Convert to PDF."""
        if input_format == "docx":
            result = await run_skill(
                skill_name="word",
                action="convert_to_pdf",
                arguments={
                    "file_path": input_file,
                    "output_path": output_path,
                },
            )
        elif input_format in ["markdown", "txt"]:
            result = await run_skill(
                skill_name="filesystem",
                action="read",
                arguments={"path": input_file},
            )
            if result.get("error"):
                return AgentResult(success=False, error_message=result["error"])

            content = result.get("content", "")
            result = await run_skill(
                skill_name="pdf",
                action="create",
                arguments={
                    "content": content,
                    "output_path": output_path or input_file.replace(f".{input_format}", ".pdf"),
                },
            )
        else:
            return AgentResult(
                success=False,
                error_message=f"Cannot convert {input_format} to PDF",
            )

        return self._process_result(result, output_path, "pdf")

    async def _to_markdown(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_path: str | None,
    ) -> AgentResult:
        """Convert to Markdown."""
        if input_format in ["pdf", "docx"]:
            skill_name = "pdf" if input_format == "pdf" else "word"
            result = await run_skill(
                skill_name=skill_name,
                action="to_markdown" if skill_name == "word" else "parse",
                arguments={"file_path": input_file},
            )
        else:
            result = await run_skill(
                skill_name="filesystem",
                action="read",
                arguments={"path": input_file},
            )

        return self._process_result(result, output_path, "md")

    async def _to_csv(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_path: str | None,
        workspace_root: str,
    ) -> AgentResult:
        """Convert to CSV (for tabular data)."""
        if input_format == "json":
            result = await run_skill(
                skill_name="filesystem",
                action="read",
                arguments={"path": input_file},
            )
            if result.get("error"):
                return AgentResult(success=False, error_message=result["error"])

            try:
                data = json.loads(result.get("content", "[]"))
                csv_output = output_path or input_file.replace(".json", ".csv")
                result = await run_skill(
                    skill_name="excel",
                    action="write",
                    arguments={
                        "file": csv_output,
                        "path": csv_output,
                        "data": data,
                        "format": "csv",
                    },
                )
                if not result.get("error"):
                    workspace_dir = Path(workspace_root or get_config().paths.user_workspace())
                    resolved_csv = Path(result.get("file") or csv_output)
                    if not resolved_csv.is_absolute():
                        resolved_csv = (workspace_dir / (output_path or csv_output)).resolve()
                    if not resolved_csv.exists():
                        return AgentResult(
                            success=False,
                            error_message=f"CSV write reported success but file is missing: {resolved_csv}",
                        )
            except json.JSONDecodeError as e:
                return AgentResult(success=False, error_message=f"Invalid JSON: {e}")
        else:
            return AgentResult(
                success=False,
                error_message=f"Cannot convert {input_format} to CSV",
            )

        return self._process_result(result, output_path, "csv", workspace_root)

    async def _to_docx(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_path: str | None,
    ) -> AgentResult:
        """Convert to Word document."""
        if input_format in ["markdown", "txt"]:
            result = await run_skill(
                skill_name="word",
                action="from_markdown" if input_format == "markdown" else "create",
                arguments={
                    "file_path": input_file,
                    "output_path": output_path,
                },
            )
        else:
            return AgentResult(
                success=False,
                error_message=f"Cannot convert {input_format} to DOCX",
            )

        return self._process_result(result, output_path, "docx")

    async def _to_txt(
        self,
        run_skill: SkillRunner,
        input_file: str,
        input_format: str,
        output_path: str | None,
    ) -> AgentResult:
        """Extract text content."""
        if input_format == "pdf":
            result = await run_skill(
                skill_name="pdf",
                action="parse",
                arguments={"file_path": input_file},
            )
        elif input_format in ["docx", "word"]:
            result = await run_skill(
                skill_name="word",
                action="parse",
                arguments={"file_path": input_file},
            )
        else:
            result = await run_skill(
                skill_name="filesystem",
                action="read",
                arguments={"path": input_file},
            )

        return self._process_result(result, output_path, "txt")

    def _process_result(
        self,
        skill_result: Dict[str, Any],
        output_path: str | None,
        ext: str,
        workspace_root: str | None = None,
    ) -> AgentResult:
        """Process skill result into AgentResult."""
        if skill_result.get("error"):
            return AgentResult(
                success=False,
                error_message=skill_result["error"],
            )

        output_file = (
            output_path
            or skill_result.get("output_path")
            or skill_result.get("file_path")
            or skill_result.get("file")
        )
        normalized_output = self._normalize_output_path(output_file, workspace_root or str(get_config().paths.user_workspace()))

        return AgentResult(
            success=True,
            output={
                "output_file": normalized_output or output_file,
                "format": ext,
                "preview": skill_result.get("content", "")[:500] if isinstance(skill_result.get("content"), str) else None,
            },
        )
