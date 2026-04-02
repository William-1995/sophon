"""PDF tool skill safety and preview limits.

Constants:
    PDF_MAX_PAGES: Hard cap on pages processed per document.
    OBSERVATION_PREVIEW_LEN: Max chars for observation text preview.
"""

# Max pages to process (safety limit for large scanned PDFs)
PDF_MAX_PAGES = 500
# Preview length for observation (characters)
OBSERVATION_PREVIEW_LEN = 500
