# Sophon Changelog

Recent changes and optimizations.

---

## 2026-02-21 (HITL: delete confirm only by default)

- **`config.ReactConfig.hitl_enabled`**: Default **`false`** (`SOPHON_HITL_ENABLED` unset or `0`); set `SOPHON_HITL_ENABLED=1` to inject `request_human_decision`. Filesystem delete still uses `__decision_request` without this flag.
- **`prompt_fragments.MULTIPART_STRICT`**: Removed encouragement to use `request_human_decision`; pause only when the user is genuinely ambiguous.
- **`build_hitl_tool()`** description: Clarifies optional / not for delete; delete uses filesystem flow.
- **Docs**: `.env.example`, `ARCHITECTURE.md`, `README.md` (HITL defaults).

---

## 2026-02-21 (workflow resilience)

- **`SKILL.md`**: **Robustness** section—document first-failure stall; expect continue + summarize successes/failures.
- **`scripts/run.py`**: Appends **`_INNER_SYSTEM_RESILIENCE`** to inner `system_prompt`; **`summarize_guidance`** asks for a **Failures** section when tools errored.

---

## 2026-02-21 (Skill routing: excel vs workflow)

- **`skills/tools/excel/SKILL.md`**: Frontmatter description + scope—**simple** spreadsheet I/O; combined multi-source / web pipelines → prefer **workflow**, use excel for direct or final sheet steps.
- **`skills/optional/work/workflow/SKILL.md`**: Shorter description; orchestration clarifies **when workflow vs excel alone**.
- **`core/react/skill_selection.py`**: Round-1 picker stays **generic**—no orchestration by skill name in the system prompt; pick from list descriptions only. (Removed named-skill routing lines.)
- **`prompt_fragments.EXEC_DISCIPLINE`**: No assumption of excel/spreadsheets; **tool(s)** wording only; “use the tools you actually have” vs prose.

---

## 2026-02-20 (HITL / execution tone)

- **`prompt_fragments.EXEC_DISCIPLINE`**: When the user assigns a task, treat the goal as clear and execute; only stop to ask or explain when the run cannot proceed.
- **`core/react/preparation.build_hitl_tool()`** (`request_human_decision`): Execute first for clear tasks; use HITL only when stuck or missing non-inferrable input.

---

## 2026-02-20 (constants / magic numbers)

### Centralized literals (`constants.py` + call sites)

- **Emotion**: `emotion-awareness/scripts/run.py` and `_lib/analyzer.py` — defaults, observation preview count/length, segment/trace limits use named constants.
- **Shared**: date prefix lengths, `END_OF_DAY_INCLUSIVE_OFFSET_SECONDS`, IPC frame `IPC_MESSAGE_LENGTH_PREFIX_BYTES`, progress URL/query previews, search/crawl defaults, trace/log-analyze limits, memory snippets, task_plan truncations, ReAct checkpoint/debug previews, API/workspace/async/OpenAI-compat lengths, DB checkpoints/traces/memory_cache, deep-research previews, workflow logging/search, log-analyze `query.py`, time `convert`/`calculate`.

---

## 2026-02-20 (ReAct execution)

### Anti–empty-tool rounds (prose-only “I will…”)

- **`core/react/tool_parsing.py`**: When tools are enabled, a round with **no** `tool_calls` no longer treats plain assistant prose as `direct_answer` (only explicit `{"answer": "..."}` JSON can short-circuit). Prevents exiting without ever invoking skills.
- **`core/react/rounds.py`**: If there are still **no observations** and the model returns no tools, append **`AGENT_LOOP_FORCE_TOOL_MSG`** and **continue** (up to **`REACT_MAX_EMPTY_TOOL_FORCE`** in `constants.py`), instead of jumping straight to summarize.
- **`MutableRunState.empty_tool_force_count`**: Tracks those nudges per run.
- **`core/react/question_heuristics.py`**: `question_suggests_tool_execution()` for file/URL/sheet-like questions.
- **`evaluate_observations(..., strict_tool_evidence=...)`**: Stricter eval prompt when the question matches the heuristic so “plans only” does not count as satisfied.
- **`prompt_fragments.EXEC_DISCIPLINE`**: One line clarifying that file/URL/spreadsheet work requires an actual tool call when tools are enabled.

### Excel: explicit `arguments` contract (no path guessing)

- **`core/tool_arg_coerce.py`**: Workbook path only from **`file`** or **`path`**; optional one nested **`arguments`** dict. Removed long alias list and **`_deep_scan_workbook_string`**. **`MISSING_WORKBOOK_PATH_HELP`** is self-contained (no internal doc names in model-visible errors).
- **`skills/tools/excel/scripts/*.py`**: Use that message when the path is missing.
- **`skills/tools/excel/SKILL.md`**: Dropped “recover path from nested strings”; states runtime does not guess.
- **`core/tool_builder.py`**: For **`excel`**, the OpenAI **`arguments`** description is self-contained; spells keys per `tool` action.

---

## 2026-02-21

### Centralized subprocess / repo paths

- **`core/runtime_paths.py`**: single definition of Sophon repo root, skill subprocess `PYTHONPATH` fragments (`scripts/_lib`, `<skill>/_lib`, `scripts/`, skill dir, repo, `skills/primitives`), helpers for API emotion hook.
- **`bootstrap_paths.py`** (repo root): `activate()` for `start.py`, `run_cli.py`, `run_api.py`, `run_mcp_bridge.py`; `api/main.py` still prepends repo once so `import bootstrap_paths` works under uvicorn.
- **`core/executor_subprocess.build_run_env`**: takes `script_path`; builds `PYTHONPATH` via `runtime_paths` so skill scripts **no longer** duplicate `sys.path.insert` / `parent.parent` walks.
- **Removed** dead `bootstrap_sophon_root` from `core/tool_arg_coerce.py`.
- **`pw_runtime.sophon_root`** delegates to `resolve_sophon_root_with_env()`.

---

## 2026-02-20

### `task_plan` built-in module (replaces `todos` skill)

- **Removed** `skills/primitives/todos/` (subprocess skill). **Added** `core/task_plan/`: `spec` (OpenAI tool schema + brief helpers), `prompts`, `parse`, `runner` (async LLM + HITL, same JSON contract as before).
- **`config.SkillConfig.exposed_skills`**: `todos` → **`task_plan`** (round-1 picker lists it when `multi_step` warrants human plan approval).
- **`core/skill_loader/`** (package): built-in names in `exposed_skills` / session selection merge synthetic briefs; capabilities grouped list includes `task_plan` when exposed.
- **`core/react/preparation.py`**: appends `build_task_plan_openai_tool()` when `task_plan` is in session skills; `entry_action`-style filter for `plan` only.
- **`core/react/execution.py`**: in-process `execute_task_plan`; injects `_tools_brief` for `task_plan.plan` only; HITL replay passes **`_decision_plan_snapshot`** from `__decision_request.payload.plan` (also applied to filesystem skills’ two-phase flow when payload carries `plan`).
- **Removed** `core/todos_plan_parse.py`, `core/react/planning.py` (dead duplicate).

---

## 2025-02-21

### ReAct: reduce “plan + confirm” stalling

- **`core/react/skill_selection.py`**: `multi_step: true` only when human plan approval is appropriate; include **`todos`** in `skills` in that case. Executable specs (paths, sheets, exports) → **`multi_step: false`**.
- **`core/react/preparation.py`**: removed **auto-inject `todos`** when `multi_part` was true (was forcing `todos.plan` / HITL).
- **`core/react/system_prompt_builder.py`**: execution discipline—no spurious confirm, no “will notify when done” without tool calls; **`multi_part`** no longer says “plan first, wait for confirm”.
- **`skills/primitives/todos/SKILL.md`**: later tightened to self-scope only (see SKILL scope cleanup).

### SKILL scope cleanup (filesystem / excel / todos)

- **SKILL.md policy**: each skill doc describes **only** that skill’s tools and scope—no prescribing other skills by name for orchestration.
- **`filesystem`**: scope for list/read/write/…; `read` = text-line oriented; honesty rule uses **this** skill’s `write`/`list` only.
- **`excel`**: scope = read/write/list_sheets/structure/to_csv and return shapes only.
- **`todos`**: scope = when `plan` + HITL fits; removed lists of other skill names.

### Excel / `tool_arg_coerce`: workbook path resilience

- **`normalize_workbook_path_string`**: strips leading **`@`** (chat refs like `@docs/file.xlsx`).
- More alias keys: `excel_file`, `workbook_file`, `source_file`, `target_file`, `path_to_excel`, `spreadsheet_file`.
- **`_deep_scan_workbook_string`**: if `file`/`path` omitted, first nested string ending in `.xlsx`/`.xls`/`.xlsm`/`.csv` is used (reduces `excel.structure` / `read` “file or path parameter is required” when the model nests the path).

### Shared todo plan parsing + agent_loop parallelism

- **`core/todos_plan_parse.py`**: `try_parse_todos_from_llm_content` / `normalize_todo_items` — single source used by **`core/react/planning.py`** and **`skills/primitives/todos/scripts/plan.py`** (removed duplicate `_try_parse_todos` / `_normalize_todos`).
- **`core/agent_loop.py`**: `_execute_calls` respects **`config.react.max_parallel_tool_calls`** via `asyncio.Semaphore` + `gather` when `max_parallel > 1` and multiple calls; preserves call order in observations; `max_parallel <= 1` or a single call keeps the previous sequential path.

---

## 2025-02-20

### Workspace multi-file upload (UI + API)

- **`POST /api/workspace/upload`**: multipart `files` + optional `subdir` (see `docs/API.md`). Handler uses `Annotated[list[UploadFile], File()]` for reliable multi-part parsing.
- **Frontend**: attach button adds **pending** files; chat area shows **Pending attachments** chips (filenames) above the input; **Send** uploads to `workspace/<user>/docs/` then sends the message with `@path` refs appended. Partial failures show in `.attachment-hint`. Styles: `.pending-attachments`, `.btn-upload`, `.sr-only`.
- **Upload-only**: if the text field is empty and the user only sends attachments, only **`POST /api/workspace/upload`** runs — **no** `sendMessage` / **`/api/chat`** (no LLM).

---

## 2025-02 (Token Optimization & Multi-Part Handling)

### Excel: `path` ↔ `file` alias

- **`core/tool_arg_coerce.py`**: `workbook_path_from_dict` / `workbook_path_from_tool_stdin` — many alternate keys (`filepath`, `workbook`, nested `arguments`/`params`, etc.) plus full stdin envelope scan.
- **`excel`**: `read`, `list_sheets`, `structure`, `write` use **`workbook_path_from_tool_stdin`**.
- *(Removed `excel-ops` optional work skill; use `excel` + `search`/`crawler` via main agent or `workflow` for mixed ingest workflows.)*

### Filesystem SKILL guidance

- `skills/primitives/filesystem/SKILL.md`: orchestration says **do not** `filesystem.read` for xlsx/pdf/docx; use **excel** / **pdf** / **word** or **workflow**; Sophon docs and skill README reads now live in the `docs` skill.

### New optional work skill: `workflow`

- Personal-scale **unstructured → structured** workflows: ingest PDF/Word/Excel/text from workspace, `fetch` URLs, `search` / `crawler`, `filesystem` list/save.
- Entry: `workflow.run` (inner tool agent). See `skills/optional/work/workflow/SKILL.md`.
- `config.SkillConfig.exposed_skills` includes `workflow`; `SKILL_TIMEOUT_OVERRIDES` default 600s.

### Token Consumption Optimizations

1. **Compact tools (round 2+)**
   - Round 1: Full tool definitions (full descriptions, sections).
   - Round 2+: Compact tools (description truncated to 120 chars) to reduce context growth.
   - See `core/tool_builder.py` `build_compact_tools_from_full()`, constants `TOOL_COMPACT_*`.

2. **Old-round observation summarization**
   - When observations exceed `OBSERVATIONS_KEEP_FULL_TAIL` (3), older observations use brief form (80 chars each).
   - Recent observations stay full. Reduces token growth across rounds.
   - See `core/react/utils.py` `truncate_observations_for_llm(summarize_old=True)`.

3. **Cross-run context condensation**
   - Initial context (past Q&A from previous runs) is condensed before injection: user messages up to 200 chars, assistant messages up to 120 chars.
   - Only applies to cross-run history via `build_chat_context`; within-run ReAct messages stay full for continuity.
   - See `api/utils.py` `condense_context_for_llm()`, constants `CONTEXT_USER_BRIEF_MAX`, `CONTEXT_ASSISTANT_BRIEF_MAX`.

### Multi-Part Request Handling

4. **LLM-based multi-step detection (replaces regex heuristic)**
   - `select_skills_for_question` now returns `multi_step`: true when the request has multiple distinct sub-tasks requiring todos.plan (e.g. "search X and write to file Y"); false for single coherent questions (e.g. "What is Python and how to install it").
   - Avoids false positives from conjunction words like "and" in "What is X and why".
   - Heuristic `_detect_multi_part_request` kept only when `skill_filter` is set (no skill selection LLM call).
   - See `core/react/skill_selection.py`, `preparation.py` `_resolve_react_skills()`.

5. **Stricter evaluation for multi-part**
   - `evaluate_observations` uses stricter prompt when `multi_part=True`: satisfied only when observations cover all sub-tasks.
   - See `core/agent_loop.py` `evaluate_observations(multi_part=...)`.

6. **Skip second HITL after plan confirmed (protocol + events, not skill names)**
   - Skills emit `SophonSkillEventType.PLAN_CONFIRMED` after plan approval; `run_react` event wrapper sets `state.plan_confirmed`.
   - `__decision_request` may set payload `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED` so the executor auto-picks confirm when `plan_confirmed` is true.
   - See `constants.py` (`SophonSkillEventType`, `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED`), `docs/ARCHITECTURE.md` *Main agent vs skills*.

### Token Metrics & Logging

7. **Full token recording**
   - Every step records tokens to `metrics` (name `llm_tokens`) and `logs`:
     - `select_skills`, `llm_round`, `skill`, `evaluate`, `summarize`, `run_total`.
   - Tags: `step`, `session_id`, `run_id`, `round` (where applicable).
   - See `preparation.py`, `rounds.py`, `finalization.py`, `core/react/main.py`, `executor_output.py`.

8. **Skill token reporting**
   - Skills can return `"tokens": N` in JSON output; merged into `state.total_tokens`.
   - `todos.plan` (and some other skills) return tokens.

9. **`run_id` in context**
   - `ImmutableRunContext.run_id` added; fixes "run_id is not defined" in metrics.
   - Preparation sets `ctx.run_id`; rounds/finalization use `ctx.run_id` for tags.

### Capabilities Output

10. **Brief capabilities**
   - `capabilities.list` returns skill names only (no per-skill description).
   - LLM summarizes when user asks "what can you do".
   - See `skills/primitives/capabilities/scripts/list.py`.

11. **Capabilities tool scope**
   - Internal `capabilities` is merged into ReAct only when `skill_filter` is `capabilities` or round-1 skill selection includes it—no user-text regex in orchestration.
   - See `core/react/preparation.py` (`_include_capabilities_internal_tool`), `constants.py` (`CAPABILITIES_SKILL_NAME`), `core/react/skill_selection.py`, `skills/primitives/capabilities/SKILL.md`.

### New Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `TOOL_COMPACT_DESC_MAX` | 120 | Max chars for tool description in compact mode |
| `TOOL_COMPACT_ORCHESTRATION_MAX` | 400 | Compact orchestration section |
| `TOOL_COMPACT_TOOLS_SECTION_MAX` | 500 | Compact tools section |
| `OBSERVATIONS_KEEP_FULL_TAIL` | 3 | Keep this many recent observations in full |
| `OBSERVATION_BRIEF_MAX` | 80 | Max chars per obs in brief (old-round) form |
| `CONTEXT_USER_BRIEF_MAX` | 200 | Max chars per user message in condensed cross-run context |
| `CONTEXT_ASSISTANT_BRIEF_MAX` | 120 | Max chars per assistant message in condensed cross-run context |
| `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED` | `"auto_confirm_if_plan_confirmed"` | `__decision_request` payload key for executor auto-confirm |
| `SophonSkillEventType.PLAN_CONFIRMED` | `"PLAN_CONFIRMED"` | Skill IPC event; orchestration sets `plan_confirmed` |
| `REACT_MULTI_PART_CONJUNCTION_PATTERN` | (regex string) | Multi-part heuristic when `skill_filter` is set |
| `REACT_MULTI_PART_LIST_SEPARATOR_PATTERN` | (regex string) | Multi-part heuristic: comma/semicolon-separated items |
