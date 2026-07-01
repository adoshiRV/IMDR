"""Spider digest → branded .docx renderer (throwaway playground tooling).

Renders a Spider content MD (daily or weekly macro research digest) into a
self-contained RV-Capital-branded Word document. It is a *generic* markdown
renderer — Spider writes the MD, this turns it into the .docx — so there are no
hard-coded content blocks to keep in sync (unlike Jonah's renderer).

Supported markdown: h1/h2/h3 (`#`/`##`/`###`), bullet lists (`- `/`* `),
GFM pipe tables, `---` rules, paragraphs, and inline `**bold**`.

Usage:
    python playground/research/_build_spider_docx.py IN.md [-o OUT.docx]

If -o is omitted the .docx is written next to the MD with the same stem.
This is playground demo tooling — not production, do not promote.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Inches

# --- RV brand palette (from rv_tokens.css) --------------------------------
RV_GREEN = RGBColor(0x00, 0x45, 0x27)
RV_DARK_BLUE = RGBColor(0x00, 0x18, 0x30)
RV_CREAM = "E1D7C0"          # shading fills use hex strings
RV_GREEN_15 = "E0E9E4"
RV_GREEN_70 = RGBColor(0x4D, 0x80, 0x6A)
RV_GREY = RGBColor(0x7A, 0x7C, 0x7C)
BODY_FONT = "Public Sans"
DISPLAY_FONT = "Newsreader"

_REPO = Path(__file__).resolve().parents[2]
_LOGO = _REPO / "docs/admin/research/brief_assets/RV_Logo_Colour.png"


def _shade(cell, hex_fill: str) -> None:
    """Set a table cell background fill."""
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def _bold_runs(paragraph, text: str, *, color: RGBColor | None = None,
               size: int | None = None) -> None:
    """Add text to a paragraph, honouring **bold** inline markers."""
    for i, seg in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not seg:
            continue
        run = paragraph.add_run(seg)
        run.bold = i % 2 == 1
        run.font.name = BODY_FONT
        if color is not None:
            run.font.color.rgb = color
        if size is not None:
            run.font.size = Pt(size)


def _masthead(doc: Document, title: str) -> None:
    if _LOGO.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run().add_picture(str(_LOGO), width=Inches(1.6))
    h = doc.add_paragraph()
    r = h.add_run(title)
    r.font.name = DISPLAY_FONT
    r.font.size = Pt(20)
    r.font.bold = True
    r.font.color.rgb = RV_GREEN
    sub = doc.add_paragraph()
    sr = sub.add_run("RV Capital · Macro Research Digest (Spider · demo)")
    sr.font.name = BODY_FONT
    sr.font.size = Pt(9)
    sr.font.color.rgb = RV_GREY
    doc.add_paragraph()  # spacer


def _footer(doc: Document) -> None:
    section = doc.sections[0]
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RV Capital — internal research. Sell-side views are the "
                  "banks' own, not RV's. Grounded to IMDR; flags mark anything "
                  "not fully sourced.")
    r.font.name = BODY_FONT
    r.font.size = Pt(7.5)
    r.font.color.rgb = RV_GREY


def _flush_table(doc: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(rows):
        for ci in range(ncol):
            cell = table.cell(ri, ci)
            cell.text = ""
            para = cell.paragraphs[0]
            text = row[ci] if ci < len(row) else ""
            if ri == 0:
                _shade(cell, "004527")
                run = para.add_run(re.sub(r"\*\*", "", text))
                run.bold = True
                run.font.name = BODY_FONT
                run.font.size = Pt(8.5)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            else:
                if ri % 2 == 0:
                    _shade(cell, RV_GREEN_15)
                _bold_runs(para, text, size=8.5)
    doc.add_paragraph()


def render(md_path: Path, out_path: Path) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()

    # strip YAML front matter
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            lines = lines[end + 1:]

    doc = Document()
    for st in doc.styles:
        try:
            st.font.name = BODY_FONT
        except Exception:
            pass

    title = "Macro Research Digest"
    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    _masthead(doc, title)

    tbl_buf: list[list[str]] = []
    first_h1_used = False

    def flush():
        nonlocal tbl_buf
        _flush_table(doc, tbl_buf)
        tbl_buf = []

    for ln in lines:
        raw = ln.rstrip()
        # GFM table row
        if raw.lstrip().startswith("|") and raw.rstrip().endswith("|"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if cells and all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            tbl_buf.append(cells)
            continue
        flush()

        if not raw.strip():
            continue
        if raw.startswith("# "):
            if first_h1_used:  # already used as masthead title
                p = doc.add_paragraph()
                r = p.add_run(raw[2:].strip())
                r.font.name = DISPLAY_FONT
                r.font.size = Pt(16)
                r.bold = True
                r.font.color.rgb = RV_GREEN
            first_h1_used = True
        elif raw.startswith("## "):
            p = doc.add_paragraph()
            r = p.add_run(raw[3:].strip())
            r.font.name = DISPLAY_FONT
            r.font.size = Pt(14)
            r.bold = True
            r.font.color.rgb = RV_GREEN
        elif raw.startswith("### "):
            p = doc.add_paragraph()
            r = p.add_run(raw[4:].strip())
            r.font.name = BODY_FONT
            r.font.size = Pt(11)
            r.bold = True
            r.font.color.rgb = RV_GREEN_70
        elif raw.strip() in ("---", "***", "___"):
            doc.add_paragraph()
        elif re.match(r"^\s*[-*]\s+", raw):
            p = doc.add_paragraph(style="List Bullet")
            _bold_runs(p, re.sub(r"^\s*[-*]\s+", "", raw), size=10)
        else:
            p = doc.add_paragraph()
            _bold_runs(p, raw.strip(), size=10)

    flush()
    _footer(doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a Spider digest MD to branded .docx")
    ap.add_argument("md", type=Path, help="input content markdown")
    ap.add_argument("-o", "--out", type=Path, default=None, help="output .docx path")
    args = ap.parse_args()
    out = args.out or args.md.with_suffix(".docx")
    render(args.md, out)


if __name__ == "__main__":
    main()
