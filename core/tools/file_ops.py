"""File operations tools for reading workspace files."""

from pathlib import Path
from typing import Any, Dict

from . import tool


def _missing_dependency(error: str) -> Dict[str, Any]:
    return {"success": False, "error": error, "content": "", "data": []}


@tool("read_file", "Read a text file")
async def read_file_tool(
    file_path: str,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """Read a local text file."""
    path = Path(file_path)
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "content": "",
        }

    content = path.read_text(encoding=encoding)
    return {
        "success": True,
        "content": content,
        "file_path": file_path,
        "size": len(content),
    }


@tool("read_pdf", "Read and extract text from a PDF file")
async def read_pdf_tool(
    file_path: str,
) -> Dict[str, Any]:
    """Read a PDF file using pdfplumber if available."""
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError:
        return _missing_dependency("pdfplumber not installed")

    path = Path(file_path)
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "content": "",
        }

    content_parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                content_parts.append(text)

        pages = len(pdf.pages)

    content = "\n\n".join(content_parts)
    return {
        "success": True,
        "content": content,
        "file_path": file_path,
        "pages": pages,
    }


@tool("read_excel", "Read an Excel file and extract data")
async def read_excel_tool(
    file_path: str,
    sheet_name: str | None = None,
) -> Dict[str, Any]:
    """Read Excel content using pandas if available."""
    try:
        import pandas as pd  # type: ignore[import]
    except ImportError:
        return _missing_dependency("pandas not installed")

    path = Path(file_path)
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "data": [],
        }

    df = pd.read_excel(path, sheet_name=sheet_name) if sheet_name else pd.read_excel(path)
    data = df.to_dict(orient="records")
    return {
        "success": True,
        "data": data,
        "file_path": file_path,
        "columns": list(df.columns),
        "rows": len(df),
    }
