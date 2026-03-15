"""
Filesystem skill adapter - registers path extractors for path-based locking.

When tools write/delete/rename, the framework acquires locks on affected paths
to prevent races. This adapter declares how to extract paths from arguments.
"""

from core.path_lock import register_path_extractor


def _paths_for_write(args: dict) -> list[str]:
    path = args.get("path")
    return [path] if path else []


def _paths_for_delete(args: dict) -> list[str]:
    path = args.get("path")
    files = [f for f in args.get("files") or [] if isinstance(f, str)]
    return sorted(set(filter(None, [path] + files)))[:3]


def _paths_for_rename(args: dict) -> list[str]:
    return sorted(set(filter(None, [args.get("path"), args.get("new_name")])))[:2]


def _register() -> None:
    register_path_extractor("filesystem", "write", _paths_for_write)
    register_path_extractor("filesystem", "delete", _paths_for_delete)
    register_path_extractor("filesystem", "rename", _paths_for_rename)


_register()
