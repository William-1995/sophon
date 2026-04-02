"""Sophon HTTP API package: FastAPI routes, handlers, and shared utilities.

Exports ``EventType`` for typed SSE and lifecycle events. On Windows, sets the
event loop policy for subprocess support before any loop is created.
"""
import asyncio
import sys

# Windows: ProactorEventLoop supports subprocess; must be set before event loop creation.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from api.schemas.event_types import EventType

__all__ = ["EventType"]
