#!/usr/bin/env python3
"""List sheets in Excel file (relative to workspace/<user_id> by default)."""
import json
import sys
from pathlib import Path

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False


def _resolve_path(params: dict, file_path: str) -> Path:
    """Resolve file path. workspace_root is already workspace/<user_id>."""
    p = Path(file_path)
    if p.is_absolute():
        return p
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    user_id = str(params.get("user_id") or "default_user")
    # workspace_root = workspace/<user_id>; strip leading user_id if caller passed it
    if p.parts and p.parts[0] == user_id:
        p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path(".")
    return workspace_root / p


def main() -> None:
    params = json.load(sys.stdin)
    args = params.get("arguments") or params
    file_path = args.get("file", "")

    if not file_path:
        print(json.dumps({"error": "file parameter is required"}))
        return

    full_path = _resolve_path(params, str(file_path))
    if not full_path.exists():
        print(json.dumps({"error": f"File not found: {full_path}"}))
        return

    suffix = full_path.suffix.lower()

    try:
        if suffix == ".xlsx":
            if not HAS_OPENPYXL:
                print(json.dumps({"error": "openpyxl not installed"}))
                return
            wb = openpyxl.load_workbook(full_path, read_only=True)
            sheets = wb.sheetnames
        elif suffix == ".xls":
            if not HAS_XLRD:
                print(json.dumps({"error": "xlrd not installed"}))
                return
            wb = xlrd.open_workbook(str(full_path))
            sheets = wb.sheet_names()
        else:
            print(json.dumps({"error": f"Not an Excel file: {suffix}"}))
            return

        print(json.dumps({"sheets": sheets}, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
