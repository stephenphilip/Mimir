"""Normalize LLM-generated Python before subprocess execution."""

from __future__ import annotations

import re
from typing import List


def prepare_execution_code(code: str, artifacts_dir: str) -> str:
    """
    Inject cwd, fix common import mistakes (FPDF, pandas, matplotlib).

    LLMs often write `import fpdf` then `FPDF()` or omit imports entirely.
    """
    body = code.strip()
    preamble: List[str] = [
        "# --- Mimir execution bootstrap (auto-injected) ---",
        "import os",
        f"os.chdir({artifacts_dir!r})",
    ]

    if _uses(r"\bFPDF\s*\(", body) and not _has(r"from\s+fpdf\s+import\s+FPDF", body):
        preamble.append("from fpdf import FPDF")

    if _uses(r"\bfpdf\.FPDF\s*\(", body) and not _has(r"import\s+fpdf", body):
        preamble.append("import fpdf")

    if _uses(r"\bpd\.", body) and not _has(r"import\s+pandas", body):
        preamble.append("import pandas as pd")

    if _uses(r"\bplt\.", body) and not _has(r"import\s+matplotlib", body):
        preamble.append("import matplotlib.pyplot as plt")

    if _uses(r"\bnp\.", body) and not _has(r"import\s+numpy", body):
        preamble.append("import numpy as np")

    if _uses(r"\bWorkbook\s*\(", body) and not _has(r"from\s+openpyxl", body):
        preamble.append("from openpyxl import Workbook")

    return "\n".join(preamble) + "\n\n" + body


def looks_like_pdf_task(code: str, user_prompt: str = "") -> bool:
    blob = f"{code}\n{user_prompt}".lower()
    return any(k in blob for k in ("fpdf", ".pdf", "pdf.output", "generate pdf", "create pdf"))


def _uses(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text))


def _has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text))
