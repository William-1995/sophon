"""
API package - FastAPI application for Sophon.

This package provides a modular FastAPI application with:
- Type-safe event handling via EventType enum
- Clear separation of concerns
- Modular route handlers
"""

from api.event_types import EventType

__all__ = ["EventType"]
