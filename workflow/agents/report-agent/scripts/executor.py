"""Cowork report agent: render research payloads into a report string (format from task)."""

from typing import Any, Dict, List
from datetime import datetime

from core.cowork import AgentContext, AgentResult, AgentExecutor


class ReportExecutor(AgentExecutor):
    """Builds markdown-style reports from ``research_data`` and optional validation hints."""

    async def execute(
        self,
        context: AgentContext,
        task: Dict[str, Any],
    ) -> AgentResult:
        """Format ``task["research_data"]`` into ``output_format`` (default markdown).

        Args:
            context (AgentContext): Agent runtime context.
            task (dict[str, Any]): Requires ``research_data``; optional ``validation_result``, ``output_format``.

        Returns:
            AgentResult: Report text in ``output`` or error.
        """
        research_data = task.get("research_data")
        validation_result = task.get("validation_result")
        output_format = task.get("output_format", "markdown")
        
        if not research_data:
            return AgentResult(
                success=False,
                error_message="No research data provided",
            )
        
        try:
            # Get raw data
            query = research_data.get("query", "Research Report")
            urls = research_data.get("urls", [])
            crawled = research_data.get("crawled_data", [])
            
            # Build report - no hardcoded assumptions about content structure
            report_lines = [
                f"# Report: {query}",
                "",
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "",
                "## Sources",
                f"Total sources found: {len(urls)}",
                f"Sources crawled: {len(crawled)}",
                "",
            ]
            
            # List all URLs
            if urls:
                report_lines.append("### URL List")
                report_lines.append("")
                for i, url in enumerate(urls, 1):
                    report_lines.append(f"{i}. {url}")
                report_lines.append("")
            
            # Include crawled content
            if crawled:
                report_lines.append("## Crawled Content")
                report_lines.append("")
                
                for item in crawled:
                    url = item.get("url", "Unknown")
                    content = item.get("content", "")
                    
                    if content:
                        report_lines.append(f"### Source: {url}")
                        report_lines.append("")
                        report_lines.append(content)
                        report_lines.append("")
            
            # Include validation info if available
            if validation_result:
                report_lines.append("## Validation")
                report_lines.append("")
                report_lines.append(f"Passed: {validation_result.get('passed', False)}")
                report_lines.append(f"Score: {validation_result.get('score', 0)}")
                report_lines.append("")
            
            report = "\n".join(report_lines)
            
            return AgentResult(
                success=True,
                output={
                    "report": report,
                    "format": output_format,
                    "generated_at": datetime.utcnow().isoformat(),
                    "query": query,
                    "sources_count": len(urls),
                    "crawled_count": len(crawled),
                },
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                error_message=f"Report generation failed: {str(e)}",
            )
    
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "report_generation",
            "data_summarization",
        ]
