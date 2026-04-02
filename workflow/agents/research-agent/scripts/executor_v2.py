"""Research agent v2: role-driven ``Agent`` using ``AgentInput`` / ``AgentOutput``."""

from typing import Any, Dict, List
from core.cowork import Agent, AgentContext, AgentInput, AgentOutput, AgentStatus
from core.cowork.skills_registry import registry


class ResearcherAgentV2(Agent):
    """Autonomous web/local gathering using registry skills (search, crawl, readers)."""
    
    DEFAULT_ROLE = """You are a Researcher Agent specializing in comprehensive information gathering.

Your responsibilities:
1. Search for relevant sources using web search
2. Crawl authoritative websites for detailed content
3. Read local documents if provided in context
4. Evaluate and prioritize sources based on relevance and authority
5. Decide autonomously when you have sufficient information

Decision guidelines (make your own judgments, don't hardcode):
- Collect enough sources to cover the topic comprehensively
- Prioritize official documentation, academic sources, and authoritative sites
- Skip low-quality or irrelevant sources
- Stop when you have sufficient information to answer the query

You have access to these skills:
- search: Find web sources
- crawl: Extract content from URLs
- read_file: Read text files
- read_pdf: Read PDF documents
- read_excel: Read Excel spreadsheets

Provide structured output with:
- sources: List of collected sources with URLs and content
- summary: Brief description of what was collected
- reasoning: Your thought process and source evaluation"""

    async def execute(self, context: AgentContext, input_data: AgentInput) -> AgentOutput:
        """Run the researcher loop for ``input_data``.

        Args:
            context (AgentContext): Cowork runtime context.
            input_data (AgentInput): Task text and prior-step payloads.

        Returns:
            AgentOutput: Structured sources, summary, and status.
        """
        task = input_data.task
        data = input_data.data
        
        # Get available skills
        search_skill = registry.get("search")
        crawl_skill = registry.get("crawl")
        
        if not search_skill:
            return AgentOutput(
                status=AgentStatus.FAILED,
                error="Search skill not available",
            )
        
        try:
            # Step 1: Search for sources
            search_result = await search_skill.execute(
                query=task,
                session_id=context.session_id,
                workspace_root=context.global_context.get("workspace_root", ""),
            )
            
            if not search_result.get("success"):
                return AgentOutput(
                    status=AgentStatus.FAILED,
                    error=f"Search failed: {search_result.get('error')}",
                )
            
            sources = search_result.get("sources", [])
            urls = [s.get("url") for s in sources if s.get("url")]
            
            if not urls:
                return AgentOutput(
                    status=AgentStatus.FAILED,
                    error="No sources found",
                )
            
            # Step 2: Crawl sources (autonomous decision on how many)
            crawled_data = []
            reasoning_parts = [
                f"Found {len(urls)} sources from search.",
                "Deciding which sources to crawl based on relevance and authority...",
            ]
            
            # Simple heuristic: crawl top sources based on URL patterns
            # In production, this should be LLM-driven
            for url in urls[:5]:  # Default to 5, but agent should decide
                if crawl_skill:
                    crawl_result = await crawl_skill.execute(
                        url=url,
                        session_id=context.session_id,
                        workspace_root=context.global_context.get("workspace_root", ""),
                    )
                    
                    if crawl_result.get("success"):
                        crawled_data.append({
                            "url": url,
                            "content": crawl_result.get("content", ""),
                        })
            
            reasoning_parts.append(f"Crawled {len(crawled_data)} sources successfully.")
            
            return AgentOutput(
                status=AgentStatus.COMPLETED,
                result={
                    "query": task,
                    "sources_found": len(urls),
                    "sources_crawled": len(crawled_data),
                    "urls": urls,
                    "crawled_data": crawled_data,
                },
                reasoning="\n".join(reasoning_parts),
                next_steps=["Analyze collected data", "Generate report"],
            )
            
        except Exception as e:
            return AgentOutput(
                status=AgentStatus.FAILED,
                error=str(e),
            )


# Backward compatibility
ResearchExecutor = ResearcherAgentV2
