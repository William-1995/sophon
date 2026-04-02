"""Workspace file listing, uploads, zip download, and static avatar images."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from services.workspace import (
    build_workspace_download_archive,
    get_profile_image_path,
    get_sophon_image_path,
    list_workspace_files,
    save_workspace_uploads,
)

router = APIRouter(tags=["workspace"])


@router.get("/api/workspace/files")
def get_workspace_files(q: str = "", recent_days: int = 7) -> dict:
    """List user-visible workspace files with recent files first.

    Args:
        q (str): Optional substring filter.
        recent_days (int): Lookback window for ``recent`` ordering metadata.

    Returns:
        ``files`` and ``recent`` path lists (relative to workspace root).
    """
    return list_workspace_files(q, recent_days)


@router.post("/api/workspace/upload")
async def post_workspace_upload(
    files: Annotated[list[UploadFile], File()],
    subdir: str = Form("docs"),
):
    """Save multipart uploads under ``workspace/<user>/<subdir>/``.

    Args:
        files (list[UploadFile]): One or more uploaded parts.
        subdir (str): Safe subpath under the user workspace (default ``docs``).

    Returns:
        ``saved`` paths and per-file ``errors`` from the service layer.

    Raises:
        HTTPException: 400 if no files were provided.
    """
    if not files:
        raise HTTPException(status_code=400, detail="no files")
    return await save_workspace_uploads(files, subdir)


@router.get("/api/workspace/download")
async def get_workspace_download(
    files: list[str] = Query(default_factory=list),
    archive_name: str = "workspace-files.zip",
):
    """Build a zip of selected workspace-relative file paths and return it.

    Args:
        files (list[str]): Relative paths; must pass visibility and traversal checks.
        archive_name (str): Suggested download filename stem.

    Returns:
        ``Response`` with ``application/zip`` body.

    Raises:
        HTTPException: 400 if no files or none were valid.
    """
    if not files:
        raise HTTPException(status_code=400, detail="no files")
    try:
        archive_bytes, safe_name = await build_workspace_download_archive(files, archive_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}
    return Response(content=archive_bytes, media_type="application/zip", headers=headers)


@router.get("/api/workspace/profile-image")
def get_profile_image():
    """Serve the user's profile JPEG if configured on disk.

    Returns:
        ``FileResponse`` image/jpeg.

    Raises:
        HTTPException: 404 if the file is missing.
    """
    path = get_profile_image_path()
    if path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/api/workspace/sophon-image")
def get_sophon_image():
    """Serve the Sophon avatar JPEG if present in the profile directory.

    Returns:
        ``FileResponse`` image/jpeg.

    Raises:
        HTTPException: 404 if the file is missing.
    """
    path = get_sophon_image_path()
    if path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")
