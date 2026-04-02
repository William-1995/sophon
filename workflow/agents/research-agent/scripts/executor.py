"""Cowork research agent: search + crawl skills, return raw sources for the main LLM."""

from typing import Any, Dict, List
from pathlib import Path

from core.cowork import AgentContext, AgentResult, AgentExecutor
from core.execution.bridge import execute_skill
from config import get_config


class ResearchExecutor(AgentExecutor):
    """Web research and crawl; returns raw text/URLs without quality scoring."""

    async def execute(
        self,
        context: AgentContext,
        task: Dict[str, Any],
    ) -> AgentResult:
        """Run search then crawl up to ``max_sources`` URLs.

        Args:
            context (AgentContext): Runtime context (``instance_id`` used as session).
            task (dict[str, Any]): Expects ``query`` or ``research_topic``; optional ``max_sources``.

        Returns:
            AgentResult: Raw crawl payloads or an error message.
        """
        query = task.get("query") or task.get("research_topic", "")
        if not query:
            return AgentResult(
                success=False,
                error_message="No research query provided",
            )
        
        max_sources = task.get("max_sources", 5)
        
        try:
            workspace_root = get_config().paths.user_workspace()
            
            # Search for sources
            search_result = await execute_skill(
                skill_name="search",
                action="search",
                arguments={"query": query, "num": 15},
                workspace_root=workspace_root,
                session_id=context.instance_id,
            )
            
            if search_result.get("error"):
                return AgentResult(
                    success=False,
                    error_message=f"Search failed: {search_result['error']}",
                )
            
            search_data = search_result.get("result", {})
            sources = search_result.get("sources", [])
            urls = self._extract_urls(search_data, sources)
            
            if not urls:
                return AgentResult(
                    success=False,
                    error_message="No URLs found in search results",
                )
            
            # Crawl sources
            crawled_contents = []
            
            for url in urls[:max_sources]:
                crawl_result = await execute_skill(
                    skill_name="crawler",
                    action="scrape",
                    arguments={"url": url, "wait_for": 2000},
                    workspace_root=workspace_root,
                    session_id=context.instance_id,
                )
                
                if not crawl_result.get("error"):
                    content = crawl_result.get("result", "")
                    crawled_contents.append({
                        "url": url,
                        "content": content,
                    })
            
            # Simple output - no assumptions, let LLM evaluate
            output = {
                "query": query,
                "sources_found": len(urls),
                "sources_crawled": len(crawled_contents),
                "urls": urls,
                "crawled_data": crawled_contents,
            }
            
            return AgentResult(
                success=True,
                output=output,
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                error_message=f"Research execution failed: {str(e)}",
            )
    
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "web_search",
            "content_crawling",
            "data_collection",
        ]
    
    def _extract_urls(self, search_data: Any, sources: List[Dict] = None) -> List[str]:
        """Extract URLs from search results."""
        urls = []
        
        if sources:
            for item in sources:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("link") or item.get("href")
                    if url:
                        urls.append(url)
                elif isinstance(item, str) and item.startswith("http"):
                    urls.append(item)
            if urls:
                return urls
        
        if isinstance(search_data, dict):
            results = search_data.get("results", search_data.get("organic", []))
            for item in results:
                if isinstance(item, dict):
                    url = item.get("link") or item.get("url")
                    if url:
                        urls.append(url)
                elif isinstance(item, str) and item.startswith("http"):
                    urls.append(item)
        elif isinstance(search_data, list):
            for item in search_data:
                if isinstance(item, dict):
                    url = item.get("link") or item.get("url")
                    if url:
                        urls.append(url)
                elif isinstance(item, str) and item.startswith("http"):
                    urls.append(item)
        
        return urls
