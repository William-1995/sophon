---
name: excel
description: Read, write, inspect, and convert spreadsheet files such as .xlsx, .xls, and .csv.
metadata:
  type: primitive
  dependencies: ""
---

## Scope

- Use this skill for spreadsheet data work: reading rows, writing tables, listing sheets, inspecting structure, and converting to CSV.
- It operates on workspace files and is designed for tabular data, not free-form documents.
- Use `file` as the primary path key; `path` is an alias.
- Paths are resolved relative to the workspace root.

## Tools

### read
Read data from Excel or CSV files.

### write
Write tabular data to Excel or CSV files.

### list_sheets
List sheet names in a workbook.

### structure
Inspect headers and row count for one sheet without loading full data.

### to_csv
Convert a workbook sheet to CSV.

## Usage

- Prefer `structure` before `read` on large workbooks.
- Use `read` when you need actual cell values.
- Use `write` when producing spreadsheet output from structured data.
