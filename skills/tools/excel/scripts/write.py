#!/usr/bin/env python3
"""Write data to Excel/CSV files (paths default to workspace/<user_id>).

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import csv
import json
import sys
from pathlib import Path

from core.execution.arg_coerce import MISSING_WORKBOOK_PATH_HELP, workbook_path_from_tool_stdin

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


def _resolve_path(params: dict, file_path: str) -> Path:
    """Resolve file path. workspace_root is already workspace/<user_id>."""
    p = Path(file_path)
    if p.is_absolute():
        return p
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    user_id = str(params.get("user_id") or "default_user")
    if p.parts and p.parts[0] == user_id:
        p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path(".")
    return workspace_root / p


def write_csv(file_path: Path, data: list) -> dict:
    """Write data to CSV file."""
    if not data:
        return {"error": "No data to write"}
    
    headers = list(data[0].keys())
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    
    return {"written": len(data), "file": str(file_path)}


def write_excel(file_path: Path, data: list, sheet_name: str = "Sheet1") -> dict:
    """Write data to Excel file (.xlsx)."""
    if not HAS_OPENPYXL:
        return {"error": "openpyxl not installed. Run: pip install openpyxl"}
    
    if not data:
        return {"error": "No data to write"}
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    
    headers = list(data[0].keys())
    ws.append(headers)
    
    for row in data:
        row_values = [row.get(h, "") for h in headers]
        ws.append(row_values)
    
    wb.save(file_path)
    return {"written": len(data), "file": str(file_path)}


def main() -> None:
    params = json.load(sys.stdin)
    args = params.get("arguments") or params
    file_path = workbook_path_from_tool_stdin(params)
    data = args.get("data", params.get("data", []))
    sheet = args.get("sheet", params.get("sheet", "Sheet1"))

    if not file_path:
        print(json.dumps({"error": MISSING_WORKBOOK_PATH_HELP}, ensure_ascii=False))
        return

    if not data:
        print(json.dumps({"error": "data parameter is required"}))
        return

    if not isinstance(data, list):
        print(json.dumps({"error": "data must be an array"}))
        return

    full_path = _resolve_path(params, str(file_path))
    full_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = full_path.suffix.lower()

    try:
        if suffix == ".csv":
            result = write_csv(full_path, data)
        elif suffix == ".xlsx":
            result = write_excel(full_path, data, sheet)
        else:
            # Default to CSV for unknown extensions
            result = write_csv(full_path.with_suffix(".csv"), data)

        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
