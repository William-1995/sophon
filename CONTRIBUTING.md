# Contributing to Sophon

Sophon is early-stage. Every contribution matters — a new skill, a bug fix, a documentation improvement, or a clear issue report.

---

## Ways to Contribute

| Type | Where to start |
|------|----------------|
| Bug report | [Open an issue](../../issues/new) |
| Feature request | [Start a discussion](../../discussions) |
| New skill | [docs/create-skill.md](docs/create-skill.md) |
| Documentation | Edit in-place, open a PR |
| Core improvement | Open a discussion first — core changes affect all skills |

---

## Quick Start

```bash
git clone https://github.com/William-1995/sophon.git
cd sophon

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: add DEEPSEEK_API_KEY or DASHSCOPE_API_KEY

python run_api.py
cd frontend && npm install && npm run dev
```

---

## Submitting a Pull Request

1. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-new-skill
   ```

2. Make your changes. Keep commits focused — one logical change per commit.

3. Test manually: start the server and exercise the skill or feature you changed.

4. Open a PR against `main` and describe:
   - What the change does
   - How you tested it
   - Any breaking changes

---

## Code Style

**Python:**
- No magic numbers — use `constants.py`
- Use `logger.debug/info/warning` — never `print` in core modules
- Type hints on all public functions
- One action per script file in skills

**Skills:**
- Always return `{"error": "..."}` on failure — never raise to stdout
- Validate required parameters before doing any work
- Read [docs/create-skill.md](docs/create-skill.md) before writing a new skill

**Commits:** follow [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `docs:`, `refactor:`.

---

## Adding a New Skill

Skills are the primary extension point. They require no knowledge of core internals and are the easiest way to add value to the platform.

See the full guide: [docs/create-skill.md](docs/create-skill.md)

Good first skills:
- `weather` — current conditions via Open-Meteo (free, no API key)
- `calculator` — safe arithmetic and expression evaluation
- `github` — search repositories, read issues, summarize PRs
- `database` — execute read-only SQL against a local database
- `notion` or `obsidian` — read and write personal notes

---

## Architecture Reference

```
core/react.py          ReAct loop, skill selection, orchestration
core/tool_builder.py   SKILL.md -> OpenAI function schema
core/agent_loop.py     reusable loop shared by sub-agents
core/executor.py       subprocess runner, per-skill timeout
core/skill_loader.py   SKILL.md parsing, validation, caching
core/providers.py      LLM provider abstraction
```

Do not modify core files without opening a discussion first.

---

## Reporting Bugs

A useful bug report includes:
- Git commit hash
- OS and Python version
- The question or skill that triggered the bug
- Expected vs. actual behavior
- Relevant log output (set `LOG_LEVEL=DEBUG` if needed)

---

## Community

- GitHub Discussions: questions, ideas, show-and-tell
- GitHub Issues: confirmed bugs and feature requests only
- We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)

---

## License

By contributing, you agree your contributions will be licensed under the MIT License (see [LICENSE](LICENSE)).
