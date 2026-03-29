"""Convert .docx files to well-structured Markdown.

Handles headings, paragraphs, tables, lists, and inline formatting.
Usage: python scripts/docx_to_md.py <input.docx> [output.md]
"""

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_inline_formatting(paragraph: Paragraph) -> str:
    """Extract paragraph text with bold/italic Markdown formatting."""
    parts: list[str] = []
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"
        parts.append(text)
    return "".join(parts)


def get_heading_level(paragraph: Paragraph) -> int | None:
    """Return heading level (1-9) or None if not a heading."""
    style = paragraph.style
    style_name = style.name if style else ""
    if style_name.startswith("Heading"):
        try:
            return int(style_name.split()[-1])
        except (ValueError, IndexError):
            return None
    return None


def get_list_info(paragraph: Paragraph) -> tuple[str, int] | None:
    """Detect if paragraph is a list item. Returns (marker, indent_level) or None."""
    pPr = paragraph._element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr"
    )
    if pPr is None:
        return None
    numPr = pPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"
    )
    if numPr is None:
        # Check style-based lists (List Bullet, List Number, etc.)
        style = paragraph.style
        style_name = style.name if style else ""
        if "List Bullet" in style_name or ("List" in style_name and "Bullet" in style_name):
            level = 0
            level_match = re.search(r"(\d+)$", style_name)
            if level_match:
                level = int(level_match.group(1)) - 1
            return ("-", level)
        if "List Number" in style_name:
            level = 0
            level_match = re.search(r"(\d+)$", style_name)
            if level_match:
                level = int(level_match.group(1)) - 1
            return ("1.", level)
        return None

    ilvl = numPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ilvl"
    )
    level = int(ilvl.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "0")) if ilvl is not None else 0

    # Heuristic: check if the text starts with a number pattern for ordered lists
    text = paragraph.text.strip()
    if re.match(r"^\d+[\.\)]\s", text):
        return ("1.", level)
    return ("-", level)


def table_to_markdown(table: Table) -> str:
    """Convert a Word table to a Markdown table."""
    rows: list[list[str]] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_text = cell.text.strip().replace("\n", " ")
            cells.append(cell_text)
        rows.append(cells)

    if not rows:
        return ""

    # Determine column widths for alignment
    col_count = max(len(row) for row in rows)
    # Normalize all rows to same column count
    for row in rows:
        while len(row) < col_count:
            row.append("")

    lines: list[str] = []
    # Header row
    lines.append("| " + " | ".join(rows[0]) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")
    # Data rows
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def convert_docx_to_markdown(input_path: str, output_path: str | None = None) -> str:
    """Convert a .docx file to Markdown and optionally write to file."""
    doc = Document(input_path)
    lines: list[str] = []
    prev_was_list = False
    prev_was_empty = False

    # Iterate through document body elements in order
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "tbl":
            # Find the matching Table object
            for table in doc.tables:
                if table._element is element:
                    if lines and not prev_was_empty:
                        lines.append("")
                    lines.append(table_to_markdown(table))
                    lines.append("")
                    prev_was_list = False
                    prev_was_empty = True
                    break

        elif tag == "p":
            # Find the matching Paragraph object
            para = Paragraph(element, doc)
            text = extract_inline_formatting(para)
            raw_text = para.text.strip()

            if not raw_text:
                if not prev_was_empty:
                    lines.append("")
                    prev_was_empty = True
                prev_was_list = False
                continue

            heading_level = get_heading_level(para)
            if heading_level is not None:
                if lines and not prev_was_empty:
                    lines.append("")
                lines.append(f"{'#' * heading_level} {raw_text}")
                lines.append("")
                prev_was_list = False
                prev_was_empty = True
                continue

            list_info = get_list_info(para)
            if list_info is not None:
                marker, level = list_info
                indent = "  " * level
                # Clean up text that starts with number pattern (already handled by marker)
                clean_text = text
                if marker == "1.":
                    clean_text = re.sub(r"^\d+[\.\)]\s*", "", text)
                if not prev_was_list and lines and not prev_was_empty:
                    lines.append("")
                lines.append(f"{indent}{marker} {clean_text}")
                prev_was_list = True
                prev_was_empty = False
                continue

            # Regular paragraph
            if prev_was_list and lines:
                lines.append("")
            lines.append(text)
            prev_was_list = False
            prev_was_empty = False

    result = "\n".join(lines).strip() + "\n"

    # Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
        print(f"Converted: {input_path} -> {output_path}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python docx_to_md.py <input.docx> [output.md]")
        sys.exit(1)

    input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_file = str(Path(input_file).with_suffix(".md"))

    convert_docx_to_markdown(input_file, output_file)
