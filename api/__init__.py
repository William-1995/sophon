"""
API package - FastAPI application for Sophon.

This package provides a modular FastAPI application with:
- Type-safe event handling via EventType enum
- Clear separation of concerns
- Modular route handlers
"""
import asyncio
import sys

# Windows: ProactorEventLoop supports subprocess; must be set before event loop creation.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from api.event_types import EventType

__all__ = ["EventType"]
