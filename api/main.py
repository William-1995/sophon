"""FastAPI application entry: mounts routers and runs startup database setup.

The repository root is inserted into ``sys.path`` before ``bootstrap_paths`` so
uvicorn can import ``api.main:app`` when the working directory is not the repo
root.
"""

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import bootstrap_paths  # noqa: E402

bootstrap_paths.activate()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.admin import router as admin_router
from api.routes.chat import router as chat_router
from api.routes.emotion import router as emotion_router
from api.routes.events import router as events_router
from api.routes.health import router as health_router
from api.routes.openai_compat import router as openai_router
from api.routes.runs import router as runs_router
from api.routes.sessions import router as sessions_router
from api.routes.skills import router as skills_router
from api.routes.workflow import router as workflow_router
from api.routes.workspace import router as workspace_router
from config import bootstrap, get_config
from constants import API_DESCRIPTION, API_TITLE, API_VERSION
from db.schema import configure_default_database, ensure_db_ready
from speech.router import router as speech_router

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health_router,
    skills_router,
    workspace_router,
    emotion_router,
    sessions_router,
    chat_router,
    events_router,
    runs_router,
    admin_router,
    openai_router,
    speech_router,
    workflow_router,
):
    app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    """Load config defaults, configure DB path, and ensure SQLite schema exists."""
    bootstrap()
    db_path = get_config().paths.db_path()
    configure_default_database(db_path)
    ensure_db_ready(db_path)
