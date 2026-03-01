#!/usr/bin/env python3
"""
Test function calling: sends a message that should trigger a skill tool (e.g. search),
then verifies tool_calls in the response.

Usage:
  cd sophon && python scripts/test_function_calling.py
  # With MLX local server:
  python scripts/test_function_calling.py --base-url http://localhost:8000/v1 --model Qwen/Qwen3-14B-MLX-4bit
  # With DeepSeek (requires DEEPSEEK_API_KEY):
  python scripts/test_function_calling.py --provider deepseek
  # With Qwen (requires DASHSCOPE_API_KEY):
  python scripts/test_function_calling.py --provider qwen
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.skill_loader import get_skill_loader, get_skills_for_session
from core.tool_builder import build_tools_from_skills
from core.providers import get_provider, OpenAICompatibleProvider
from core.executor import execute_skill
from config import bootstrap, get_config


async def _run_single_round(
    provider,
    tools: list[dict],
    question: str,
    workspace_root: Path,
) -> dict:
    """One LLM round with tools. Returns provider response (content, tool_calls)."""
    messages = [{"role": "user", "content": question}]
    system = (
        "You have tools. When the user asks something that needs a tool (e.g. search, list files), "
        "you MUST call the relevant tool. Reply with tool calls in OpenAI format."
    )
    resp = await provider.chat(messages, tools=tools, system_prompt=system)
    return resp


async def _run_full_react(
    provider,
    question: str,
    workspace_root: Path,
) -> tuple[str, dict]:
    """Full ReAct flow (uses run_react)."""
    from core.react import run_react
    cfg = get_config()
    db_path = cfg.paths.db_path()
    answer, meta = await run_react(
        question=question,
        provider=provider,
        workspace_root=workspace_root,
        session_id="test-fc",
        skill_filter=None,
        db_path=db_path,
    )
    return answer, meta


def main():
    parser = argparse.ArgumentParser(description="Test function calling")
    parser.add_argument(
        "--mode",
        choices=["single", "full"],
        default="full",
        help="single = one LLM round only; full = full ReAct loop",
    )
    parser.add_argument(
        "--question",
        default="Search the web for 'Python 3.12 release' and tell me one headline.",
        help="User question (should trigger a tool)",
    )
    parser.add_argument(
        "--provider",
        choices=["deepseek", "qwen"],
        default=None,
        help="Provider name. If not set, uses --base-url + --model (e.g. for MLX).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("MLX_BASE_URL", "http://localhost:8000/v1"),
        help="API base URL (for openai provider or MLX)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MLX_MODEL", "Qwen/Qwen3-14B-MLX-4bit"),
        help="Model name",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY", "not-needed"),
        help="API key (use not-needed for local MLX)",
    )
    args = parser.parse_args()

    bootstrap()
    ws = get_config().paths.user_workspace()

    if args.provider:
        provider = get_provider(name=args.provider, model=args.model)
    else:
        provider = OpenAICompatibleProvider(
            base_url=args.base_url.rstrip("/"),
            api_key=args.api_key,
            model=args.model,
        )

    loader = get_skill_loader()
    brief = get_skills_for_session(selected_skills=["search", "filesystem"])
    tools = build_tools_from_skills(brief, loader)

    print(f"[test] mode={args.mode} provider={type(provider).__name__} model={args.model}")
    print(f"[test] tools={[t['function']['name'] for t in tools]}")
    print(f"[test] question={args.question[:60]}...")
    print()

    if args.mode == "single":
        resp = asyncio.run(_run_single_round(provider, tools, args.question, ws))
        print("[test] Response content:", (resp.get("content") or "")[:300])
        tc = resp.get("tool_calls") or []
        print(f"[test] tool_calls count: {len(tc)}")
        for i, t in enumerate(tc):
            fn = t.get("function") or {}
            print(f"  [{i}] name={fn.get('name')} args={fn.get('arguments', '')[:100]}...")
        if not tc and tools:
            print("[test] WARNING: Tools were sent but no tool_calls in response. Model may not support function calling.")
    else:
        answer, meta = asyncio.run(_run_full_react(provider, args.question, ws))
        print("[test] Final answer:")
        print(answer[:500] + ("..." if len(answer) > 500 else ""))
        print(f"[test] tokens={meta.get('tokens', 0)}")


if __name__ == "__main__":
    main()
