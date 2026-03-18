# Excel-Ops Skill

Sub-agent to fill Excel columns from web/search. Key column (URL or name) → batch retrieve → LLM extract → write.

## Capabilities

- **run**: Main entry, call once
- **list_sheets**: List sheets
- **read_structure**: Headers and row count
- **read_sample**: Sample data rows
- **fill_by_column**: Batch retrieve and fill target columns

## Dependencies

- `excel`, `search`, `crawler`

## Pip Packages

From excel, search, crawler. Excel needs openpyxl (optional xlrd). Crawler needs playwright, trafilatura.

## Role

- Fill workbook columns from web or search
- Use crawler when key column looks like URL, else search
