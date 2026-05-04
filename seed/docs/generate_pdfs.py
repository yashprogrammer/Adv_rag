"""Generate PDF policy documents from .txt sources for ingestion testing.

Reads each `*.txt` file listed in `SOURCES` and produces an equivalent `*.pdf`
next to it via reportlab. Run after editing any .txt source.

Usage:
    uv pip install reportlab
    uv run python seed/docs/generate_pdfs.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

DOCS_DIR = Path(__file__).parent

SOURCES = [
    "refund-policy.txt",
    "shipping-policy.txt",
    "warranty.txt",
    "returns-sop.txt",
    "faq.txt",
]


def _escape(line: str) -> str:
    return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt_to_pdf(txt_path: Path, pdf_path: Path) -> None:
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=sample["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
    )
    title_style = ParagraphStyle(
        "title",
        parent=sample["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=12,
        alignment=0,
    )

    raw_lines = txt_path.read_text(encoding="utf-8").splitlines()
    title_text = next((line for line in raw_lines if line.strip()), txt_path.stem)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title=txt_path.stem,
        author="ADV RAG seed",
    )

    flow = [Paragraph(_escape(title_text), title_style), Spacer(1, 0.15 * inch)]
    saw_title = False
    for line in raw_lines:
        stripped = line.rstrip()
        if not stripped:
            flow.append(Spacer(1, 0.1 * inch))
            continue
        if not saw_title and stripped == title_text:
            saw_title = True
            continue
        flow.append(Paragraph(_escape(stripped), body))

    doc.build(flow)


def main() -> None:
    for fname in SOURCES:
        src = DOCS_DIR / fname
        if not src.exists():
            print(f"skip: {fname} (missing)")
            continue
        out = src.with_suffix(".pdf")
        txt_to_pdf(src, out)
        print(f"wrote: {out.name}")


if __name__ == "__main__":
    main()
