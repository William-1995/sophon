"""Word tool skill safety and preview limits.

Constants:
    OBSERVATION_PREVIEW_LEN: Max chars for observation text preview.
    WORD_MAX_PARAGRAPHS / WORD_MAX_TABLES: Extraction caps per document.
"""

# Preview length for observation (characters)
OBSERVATION_PREVIEW_LEN = 500
# Max paragraphs to extract (safety limit)
WORD_MAX_PARAGRAPHS = 10000
# Max tables to extract
WORD_MAX_TABLES = 500
