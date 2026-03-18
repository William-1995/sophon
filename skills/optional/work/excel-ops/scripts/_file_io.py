"""
Excel-Ops Enrich - I/O utilities.

Path resolution and output file handling.
"""

from pathlib import Path

from _config import MODE_OVERWRITE, OUTPUT_SUFFIX_ENRICHED, OUTPUT_SUFFIX_FILLED
from _context import ResolvedContext


def resolve_full_path(path_raw: str, ctx: ResolvedContext) -> Path:
    """Resolve relative or absolute path to full path.

    Args:
        path_raw: Raw path string (may be relative or absolute).
        ctx: Resolved context with workspace_root and user_id.

    Returns:
        Resolved absolute Path.
    """
    raw_path = Path(path_raw)

    if raw_path.is_absolute():
        return raw_path

    # Strip user_id prefix if present
    if raw_path.parts and raw_path.parts[0] == ctx.user_id:
        raw_path = (
            Path(*raw_path.parts[1:])
            if len(raw_path.parts) > 1
            else Path(".")
        )

    return (ctx.workspace_root / raw_path).resolve()


def determine_output_path(full_path: Path, mode: str) -> Path:
    """Determine output file path based on mode.

    Args:
        full_path: Full path to input file.
        mode: Output mode ("copy" or "overwrite").

    Returns:
        Path to output file.
    """
    if mode == MODE_OVERWRITE:
        return full_path

    stem = full_path.stem
    suffix = full_path.suffix

    if stem.endswith(OUTPUT_SUFFIX_FILLED):
        out_name = f"{stem}{OUTPUT_SUFFIX_ENRICHED}{suffix}"
    else:
        out_name = f"{stem}{OUTPUT_SUFFIX_FILLED}{suffix}"

    return full_path.with_name(out_name)
