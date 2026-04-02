#!/usr/bin/env python3
"""Start the Sophon HTTP API with uvicorn (reload enabled). Port: PORT or config.DEFAULT_API_PORT."""
import logging
import os
import sys

import bootstrap_paths

bootstrap_paths.activate()

from config import get_config

API_PORT = get_config().server.api_port

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=API_PORT, reload=True)
