"""Project-wide defaults that should have a single source of truth."""

DEFAULT_MODEL = "deepseek-chat"


SKILL_TIMEOUT = 30
SKILL_TIMEOUT_OVERRIDES: dict[str, int] = {
    "deep-research": 300,
    "search": 120,
    "crawler": 60,
}
