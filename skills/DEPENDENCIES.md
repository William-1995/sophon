# Skill Dependencies

pip packages and system dependencies for each skill. All skills work out of the box after `pip install -r requirements.txt`.

## Overview

| Skill | pip packages | requirements.txt | System deps | Ready |
|-------|--------------|------------------|-------------|-------|
| **pdf** | pypdf | ✅ | None | ✅ |
| **word** | python-docx | ✅ | .doc needs LibreOffice | .docx ✅ / .doc needs LibreOffice |
| **excel** | openpyxl, xlrd | ✅ | None | ✅ |
| **filesystem** | None | - | None | ✅ |
| **fetch** | httpx | ✅ | None | ✅ |
| **capabilities** | None | - | None | ✅ |
| **memory** | None | - | None | ✅ |
| **time** | None | - | None | ✅ |
| **search** | ddgs | ✅ | None | ✅ |
| **crawler** | playwright, trafilatura | ✅ | `playwright install chromium` | ✅ (start.py runs it) |
| **log-analyze** | None | - | None | ✅ |
| **trace** | None | - | None | ✅ |
| **metrics** | None | - | None | ✅ |
| **deep-research** | httpx, beautifulsoup4 | ✅ | crawler deps | ✅ |
| **excel-ops** | via excel,search,crawler | ✅ | same as crawler | ✅ |
| **troubleshoot** | via log,trace,metrics | - | None | ✅ |
| **todos** | None | - | None | ✅ |
| **emotion-awareness** | None | - | None | ✅ |

## Notes

### Word (.doc)

- **.docx**: `python-docx` only, works out of the box.
- **.doc**: Requires LibreOffice (`soffice` in PATH). Install per platform: see `tools/word/README.md`.

### Crawler (Playwright)

Run `playwright install chromium` once. `python start.py` does this automatically.

### Optional packages

- **faster-whisper**: Speech-to-text. Comment out in requirements.txt if not used.
- **msgpack**: Only when `SOPHON_IPC_FORMAT=msgpack`.
- **xlrd**: Only for .xls; omit if you only use .xlsx/.csv.

## Verify

```bash
cd sophon
pip install -r requirements.txt
playwright install chromium
python start.py
```
