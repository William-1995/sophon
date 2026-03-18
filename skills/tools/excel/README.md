# Excel Skill

Read and write Excel/CSV. Supports .xlsx, .xls, .csv.

## Capabilities

- **read**: Read cell data (sheet, limit, offset)
- **write**: Write data, overwrites existing file
- **list_sheets**: List sheet names
- **structure**: Headers and row count, no data (for large files)
- **to_csv**: Convert Excel to CSV and write to file

## Pip Packages

| Package | Purpose |
|---------|---------|
| `openpyxl` | .xlsx read/write |
| `xlrd` | .xls read (optional) |

## Role

- Structured table I/O
- Lightweight inspection (structure, list_sheets)
- Excel ↔ CSV conversion
