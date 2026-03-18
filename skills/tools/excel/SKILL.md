---
name: excel
description: Read and write Excel/CSV files. Supports .xlsx, .xls, and .csv formats.
metadata:
  type: primitive
  dependencies: ""
---

## Workspace

All file paths are relative to the workspace root.

## Tools

### read
Read data from Excel or CSV file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | string | Yes | File path relative to workspace |
| sheet | string/int | No | Sheet name or index (default: 0, first sheet) |
| limit | int | No | Maximum rows to read (default: all) |
| offset | int | No | Starting row (0-based, default: 0) |

Returns: `{headers: [...], data: [{col1: val1, ...}], total_rows: N}`

### write
Write data to Excel or CSV file. Overwrites existing file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | string | Yes | File path relative to workspace |
| data | array | Yes | Array of objects (first row is headers if dict keys used) |
| sheet | string | No | Sheet name (default: "Sheet1") |

Returns: `{written: N, file: path}`

### list_sheets
List all sheet names in an Excel file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | string | Yes | File path relative to workspace |

Returns: `{sheets: ["Sheet1", "Sheet2", ...]}`

### structure
Return headers and total row count for one sheet (no data). Lightweight for large files.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | string | Yes | File path relative to workspace |
| sheet | string/int | No | Sheet name or index (default: first) |

Returns: `{sheet, headers, total_rows}`. Not supported for CSV.

### to_csv
Convert Excel (.xlsx, .xls) to CSV and write to file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | string | Yes | Excel file path relative to workspace |
| output_path | string | Yes | Output CSV path relative to workspace |
| sheet | string/int | No | Sheet name or index (default: 0) |

Returns: `{output_path, written, rows}`. Use `output_path` when you need to convert and save.

## Output Contract

### read
```json
{
  "headers": ["h1", "h2", "h3"],
  "data": [
    {"h1": "<value>", "h2": "<value>", "h3": "<value>"},
    {"h1": "<value>", "h2": "<value>", "Country": "<value>"}
  ],
  "total_rows": 100
}
```

### write
```json
{
  "written": 50,
  "file": "output.xlsx"
}
```
