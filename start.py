#!/usr/bin/env python3
"""One-click start: install deps, ensure Playwright browser, then run API.

No need to distinguish first run vs normal. Safe to run every time.
"""
import os
import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _run(cmd: list[str], desc: str) -> bool:
    r = subprocess.run(cmd, cwd=_root, capture_output=True, text=True)
    if r.returncode != 0 and r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


def main() -> None:
    os.chdir(_root)
    py = sys.executable
    req = _root / "requirements.txt"
    if req.exists():
        _run([py, "-m", "pip", "install", "-q", "-r", str(req)], "Install deps")
    _run([py, "-m", "playwright", "install", "chromium"], "Ensure Playwright browser")

    # Start API (same logging as run_api)
    import logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    for _n in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(_n).setLevel(logging.WARNING)

    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
