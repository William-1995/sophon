"""Per-user workspace layout and SQLite location under ``workspace/<user_id>/``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .common import (
    DB_FILENAME,
    DEFAULT_USER_ID,
    PROFILE_IMAGE_FILENAME,
    SOPHON_IMAGE_FILENAME,
    WORKSPACE_DOCS_DIR,
    WORKSPACE_IMAGES_DIR,
    WORKSPACE_PROFILE_DIR,
    ROOT,
)


@dataclass(frozen=True)
class PathConfig:
    """Resolved paths for docs, images, profile assets, and the per-user database.

    Attributes:
        user_id (str): Directory name under ``workspace/`` for this config.
        workspace (Path): Parent of all user folders (default ``<ROOT>/workspace``).
    """

    user_id: str = DEFAULT_USER_ID
    workspace: Path = field(default_factory=lambda: ROOT / "workspace")

    def user_workspace(self) -> Path:
        """Return ``workspace/<user_id>/``."""
        return self.workspace / self.user_id

    def docs_dir(self) -> Path:
        """Default document root for uploads and file skills (``docs/``)."""
        return self.user_workspace() / WORKSPACE_DOCS_DIR

    def images_dir(self) -> Path:
        """User images directory (``images/``)."""
        return self.user_workspace() / WORKSPACE_IMAGES_DIR

    def profile_dir(self) -> Path:
        """Profile subdirectory for avatars (``images/profile/``)."""
        return self.user_workspace() / WORKSPACE_PROFILE_DIR

    def profile_image_path(self) -> Path:
        """Path to the user's profile JPEG (e.g. ``me.jpeg``)."""
        return self.profile_dir() / PROFILE_IMAGE_FILENAME

    def sophon_image_path(self) -> Path:
        """Path to the Sophon avatar JPEG beside the user profile."""
        return self.profile_dir() / SOPHON_IMAGE_FILENAME

    def db_path(self) -> Path:
        """SQLite file path (typically ``sophon.db`` under the user workspace)."""
        return self.user_workspace() / DB_FILENAME

    def recent_files_path(self) -> Path:
        """Alias for the DB path; recent-file metadata lives in the same database."""
        return self.db_path()

    def ensure_dirs(self) -> None:
        """Create workspace, user, docs, images, and profile directories if missing."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.user_workspace().mkdir(parents=True, exist_ok=True)
        self.docs_dir().mkdir(parents=True, exist_ok=True)
        self.images_dir().mkdir(parents=True, exist_ok=True)
        self.profile_dir().mkdir(parents=True, exist_ok=True)
