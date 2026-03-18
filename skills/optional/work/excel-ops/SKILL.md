---
name: excel-ops
description: Process xlsx workbooks; fill columns from web via key column (URL→crawl, else search), LLM extract per batch. Tools: list_sheets, read_structure, read_sample, fill_by_column. Cross-sheet copy via copy_columns / copy_column_map.
metadata:
  type: feature
  entry_action: run
  dependencies: "excel,search,crawler"
---

## Orchestration Guidance

**When to use**

- User wants to fill workbook columns from the web (URLs or search). File format: xlsx or supersets.
- The key column (e.g. URL, company name) and target columns are in the workbook; you discover them by reading the file.

**What this skill does**

- **Tools for reading**: You choose how many sheets to read. Call `list_sheets` first, then `read_structure` and/or `read_sample` for the sheet(s) you need.
- **Fill pipeline**: Call `fill_by_column` with the key column (identified from structure/sample), target columns, and optional source/target sheet. The skill batches rows, runs parallel search per batch, one LLM call per batch to extract, then writes row by row (key = key column value).

**Main agent: call `excel-ops.run` once**

- When the user wants to fill workbook columns from web/search (xlsx or superset), call `excel-ops.run(path, question)`.
- Do not orchestrate workbook operations yourself — delegate to `excel-ops.run`.

**Sub-agent: deep-excel-research (4 tools)**

The sub-agent (deep-excel-research) has four tools. It does NOT see excel, search, or crawler — those are used internally. When key column values look like URLs, fill_by_column crawls them for full page content; otherwise it searches.

1. **list_sheets**: Get sheet names. Call first to choose which sheet(s) to inspect.
2. **read_structure**: For one sheet, get headers and total row count (no data).
3. **read_sample**: For one sheet, get headers and first n_rows of data. Use this to identify the key column and target columns.
4. **fill_by_column**: Run the pipeline: read key column, batch parallel retrieve, LLM extract per batch, write back by row. Call after you know key_column and target_columns from structure/sample.

**Required flow**

1. Call **list_sheets** with path.
2. Call **read_structure** and/or **read_sample** for the relevant sheet(s) (you decide which and how many).
3. From the result, identify **key_column** (the column whose values are used for search, e.g. URL) and **target_columns** to fill.
4. Call **fill_by_column** with path, key_column, target_columns, and optional source_sheet, target_sheet, copy_columns, copy_column_map (map target column name to source column name when they differ).
5. Do NOT summarize until **fill_by_column** has been called and returned. Report output_path, processed_rows, updated_rows to the user.

## Tools

### run

Entry point. Main agent calls `excel-ops.run` once with `path` and `question`. Sub-agent uses list_sheets, read_structure, read_sample, fill_by_column.

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| path      | string | Yes      | Workbook file path (xlsx or superset) relative to workspace root |
| question  | string | Yes      | User request (target columns, which sheet, etc.) |

Returns: `{answer, observation, output_path?, ...}`

### list_sheets

List sheet names in the workbook. Call first so you can choose which sheet(s) to read.

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| path      | string | Yes      | Workbook file path (xlsx or superset) relative to workspace root |

Returns: `{sheets: string[]}`

### read_structure

For one sheet, return headers and total row count (no data rows).

| Parameter   | Type   | Required | Description |
|-------------|--------|----------|-------------|
| path        | string | Yes      | Workbook file path (xlsx or superset) relative to workspace root |
| sheet_name  | string | No       | Sheet name or index. Omit for active sheet. |

Returns: `{sheet, headers, total_rows}`

### read_sample

For one sheet, return headers and first n_rows of data.

| Parameter   | Type   | Required | Description |
|-------------|--------|----------|-------------|
| path        | string | Yes      | Workbook file path (xlsx or superset) relative to workspace root |
| sheet_name  | string | No       | Sheet name or index. Omit for active sheet. |
| n_rows      | int    | No       | Number of data rows to sample (default 2, max 20) |

Returns: `{sheet, headers, data, total_rows}` (total_rows = len(data))

### fill_by_column

Run the fill pipeline: key column -> batch parallel retrieve (search or crawl) -> LLM extract -> write by row. When key looks like URL, crawls for full page content; otherwise searches. Keys (e.g. URLs) identify rows; results are written back row by row.

| Parameter       | Type     | Required | Description |
|-----------------|----------|----------|-------------|
| path            | string   | Yes      | Workbook file path (xlsx or superset) relative to workspace root |
| key_column      | string   | Yes      | Column used as retrieve key (e.g. URL or website column) |
| target_columns  | string[] | Yes      | Column names to fill from retrieved content |
| source_sheet    | string   | No       | Sheet to read key column from. Omit for active sheet. |
| target_sheet    | string   | No       | Sheet to write to. When different from source_sheet: cross-sheet fill. |
| company_column  | string   | No       | Optional: combine with key_column for search query |
| copy_columns    | string[] | No       | Column names to copy from source to target (same name in both sheets) |
| copy_column_map | object   | No       | Map target column name to source column name when names differ. Keys = target, values = source. |
| retrieve_mode   | string   | No       | `"auto"` (crawl when key looks like URL, else search), `"crawl"`, or `"search"` |
| start_row       | int      | No       | 1-based first data row (default 2) |
| max_rows        | int      | No       | Max rows to process (omit = all) |
| batch_size      | int      | No       | Rows per batch for parallel retrieve + 1 LLM call (default 5) |
| mode            | string   | No       | `"copy"` (write *_FILLED.xlsx) or `"overwrite"` |
| instructions    | string   | No       | Instructions for LLM. If empty, default: fill every target column when content allows; empty when absent or uncertain. |

Returns: `{output_path, processed_rows, updated_rows, target_columns, copy_columns?, copy_column_map?, errors?}`

## Output Contract

| Field          | Type     | Description |
|----------------|----------|-------------|
| output_path    | string   | Output workbook path (e.g. *_FILLED.xlsx) |
| processed_rows | int      | Rows attempted |
| updated_rows   | int      | Rows with at least one target column filled |
| target_columns | string[] | Column names filled |
| errors         | object[] | Optional: {row, key, reason} for failures |
| error          | string   | Top-level error when overall failure |
