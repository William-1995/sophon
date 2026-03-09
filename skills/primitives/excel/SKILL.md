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

## Output Contract

### read
```json
{
  "headers": ["Company Name", "Website", "Country"],
  "data": [
    {"Company Name": "Nexa Labs", "Website": "nexa.farm", "Country": "US"},
    {"Company Name": "Stronic", "Website": "stronic.com", "Country": "IN"}
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
