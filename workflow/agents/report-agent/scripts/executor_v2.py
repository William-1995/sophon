"""Report / writer agent v2: role-driven ``Agent`` with ``AgentInput`` / ``AgentOutput``."""

from datetime import datetime

from core.cowork import Agent, AgentContext, AgentInput, AgentOutput, AgentStatus

class WriterAgentV2(Agent):
    """Autonomous report generation from prior-step data and task instructions."""

    DEFAULT_ROLE = """You are a Writer Agent specializing in creating high-quality structured reports.

Your responsibilities:
1. Generate reports, summaries, or other written content based on provided data
2. Structure output based on content type and audience needs
3. Use data from previous analysis steps
4. Ensure clarity, accuracy, and completeness
5. Format output appropriately (markdown, structured data, etc.)

Decision guidelines (make your own judgments):
- Determine the best report structure based on the data and task
- Include relevant details without overwhelming the reader
- Use appropriate formatting for readability
- Highlight key findings and insights

You have access to these skills:
- generate_report: Create structured reports
- format_output: Format content in specific styles

Provide structured output with:
- report: The generated report content
- format: Format used (markdown, html, etc.)
- metadata: Additional information about the report
- reasoning: Your thought process in structuring the report"""

    async def execute(self, context: AgentContext, input_data: AgentInput) -> AgentOutput:
        """Produce a structured report for ``input_data``.

        Args:
            context (AgentContext): Cowork runtime context (prior outputs).
            input_data (AgentInput): Task and source material references.

        Returns:
            AgentOutput: Report body, format metadata, and status.
        """
        task = input_data.task
        data = input_data.data

        # Get research data from previous steps
        research_data = data.get("research_data", {})
        validation_result = data.get("validation_result", {})

        query = research_data.get("query", "Research Report")
        urls = research_data.get("urls", [])
        crawled = research_data.get("crawled_data", [])

        # Generate report content (autonomous structure)
        report_lines = [
            f"# Report: {query}",
            "",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Sources",
            f"Total sources found: {len(urls)}",
            f"Sources analyzed: {len(crawled)}",
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
            report_lines.append("## Content Analysis")
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

        return AgentOutput(
            status=AgentStatus.COMPLETED,
            result={
                "report": report,
                "format": "markdown",
                "generated_at": datetime.utcnow().isoformat(),
                "query": query,
                "sources_count": len(urls),
                "crawled_count": len(crawled),
            },
            reasoning=f"Generated report based on {len(crawled)} crawled sources. "
                      f"Structured with sources list and detailed content sections.",
        )


# Backward compatibility
ReportExecutor = WriterAgentV2
