from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from talentmatch.infra.llm.prompts import strip_markdown_code_fences


@dataclass(frozen=True)
class StoreRfpPdfResult:
    """Result of storing RFP Markdown as a PDF file."""
    uuid: str


class RfpMarkdownPdfStore:
    """Stores an RFP Markdown as a PDF file under a UUID-based name."""

    def __init__(self, settings: Any) -> None:
        self._base_dir = Path(settings.paths.rfp_pdf_dir)
        self._font_name = self._register_unicode_font()

    def store(self, uuid: str, markdown: str) -> StoreRfpPdfResult:
        sanitized = strip_markdown_code_fences(markdown).strip()
        if not sanitized:
            raise ValueError("Markdown content is empty")

        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{uuid}.pdf"

        styles = getSampleStyleSheet()
        base_style = ParagraphStyle(
            name="Base",
            parent=styles["BodyText"],
            fontName=self._font_name,
            fontSize=10,
            leading=13,
            spaceAfter=4,
        )
        heading_1 = ParagraphStyle(
            name="Heading1",
            parent=base_style,
            fontSize=16,
            leading=20,
            spaceBefore=6,
            spaceAfter=10,
        )
        heading_2 = ParagraphStyle(
            name="Heading2",
            parent=base_style,
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
        )
        heading_3 = ParagraphStyle(
            name="Heading3",
            parent=base_style,
            fontSize=11,
            leading=14,
            spaceBefore=8,
            spaceAfter=4,
        )
        table_cell_style = ParagraphStyle(
            name="TableCell",
            parent=base_style,
            fontSize=9.4,
            leading=11.5,
            spaceAfter=0,
        )
        table_header_style = ParagraphStyle(
            name="TableHeader",
            parent=table_cell_style,
            fontSize=9.4,
            leading=11.5,
        )

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=f"{uuid}",
        )

        story = list(
            self._markdown_to_flowables(
                sanitized,
                base_style=base_style,
                heading_1=heading_1,
                heading_2=heading_2,
                heading_3=heading_3,
                table_cell_style=table_cell_style,
                table_header_style=table_header_style,
                available_width=A4[0] - 36 - 36,
            )
        )
        doc.build(story)

        return StoreRfpPdfResult(uuid=uuid)

    def _markdown_to_flowables(
            self,
            markdown: str,
            *,
            base_style: ParagraphStyle,
            heading_1: ParagraphStyle,
            heading_2: ParagraphStyle,
            heading_3: ParagraphStyle,
            table_cell_style: ParagraphStyle,
            table_header_style: ParagraphStyle,
            available_width: float,
    ) -> Iterable[object]:
        lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        paragraph_lines: list[str] = []
        bullet_lines: list[str] = []

        def flush_paragraph() -> Iterable[object]:
            if not paragraph_lines:
                return []
            text = " ".join(part.strip() for part in paragraph_lines if part.strip())
            paragraph_lines.clear()
            if not text:
                return []
            return [Paragraph(self._to_paragraph_markup(text), base_style), Spacer(1, 6)]

        def flush_bullets() -> Iterable[object]:
            if not bullet_lines:
                return []
            items = [
                ListItem(Paragraph(self._to_paragraph_markup(item), base_style), leftIndent=12)
                for item in bullet_lines
            ]
            bullet_lines.clear()
            return [ListFlowable(items, bulletType="bullet", leftIndent=12), Spacer(1, 6)]

        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()

            if not line:
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                i += 1
                continue

            if self._is_table_header_line(line) and i + 1 < len(lines) and self._is_table_separator_line(
                    lines[i + 1].strip()):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                table, next_index = self._parse_table(
                    lines=lines,
                    start_index=i,
                    table_cell_style=table_cell_style,
                    table_header_style=table_header_style,
                    available_width=available_width,
                )
                yield table
                yield Spacer(1, 8)
                i = next_index
                continue

            if line.startswith("# "):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                yield Paragraph(self._to_paragraph_markup(line[2:].strip()), heading_1)
                yield Spacer(1, 8)
                i += 1
                continue

            if line.startswith("## "):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                yield Paragraph(self._to_paragraph_markup(line[3:].strip()), heading_2)
                yield Spacer(1, 6)
                i += 1
                continue

            if line.startswith("### "):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                yield Paragraph(self._to_paragraph_markup(line[4:].strip()), heading_3)
                yield Spacer(1, 4)
                i += 1
                continue

            if line.startswith(("- ", "* ")):
                for f in flush_paragraph():
                    yield f
                bullet_lines.append(line[2:].strip())
                i += 1
                continue

            paragraph_lines.append(line)
            i += 1

        for f in flush_bullets():
            yield f
        for f in flush_paragraph():
            yield f

    def _parse_table(
            self,
            *,
            lines: list[str],
            start_index: int,
            table_cell_style: ParagraphStyle,
            table_header_style: ParagraphStyle,
            available_width: float,
    ) -> tuple[Table, int]:
        header_line = lines[start_index].strip()
        i = start_index + 2

        header_cells = self._split_table_row(header_line)
        body_rows: list[list[str]] = []

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                break
            if not self._looks_like_table_row(line):
                break
            body_rows.append(self._split_table_row(line))
            i += 1

        column_count = max([len(header_cells)] + [len(r) for r in body_rows] + [1])
        header_cells = self._pad_row(header_cells, column_count)
        body_rows = [self._pad_row(r, column_count) for r in body_rows]

        data: list[list[Paragraph]] = [
            [Paragraph(self._to_paragraph_markup(cell), table_header_style) for cell in header_cells],
            *[
                [Paragraph(self._to_paragraph_markup(cell), table_cell_style) for cell in row]
                for row in body_rows
            ],
        ]

        col_width = available_width / column_count
        table = Table(data, colWidths=[col_width] * column_count, repeatRows=1)

        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), table_cell_style.fontName),
                    ("FONTSIZE", (0, 0), (-1, -1), table_cell_style.fontSize),
                    ("LEADING", (0, 0), (-1, -1), table_cell_style.leading),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        return table, i

    @staticmethod
    def _looks_like_table_row(line: str) -> bool:
        return "|" in line

    @staticmethod
    def _is_table_header_line(line: str) -> bool:
        if "|" not in line:
            return False
        cells = RfpMarkdownPdfStore._split_table_row(line)
        return any(cell.strip() for cell in cells)

    @staticmethod
    def _is_table_separator_line(line: str) -> bool:
        if "|" not in line:
            return False
        allowed = set("|:- ")
        if any(ch not in allowed for ch in line):
            return False
        core = line.replace("|", "").replace(":", "").replace(" ", "")
        return core and all(ch == "-" for ch in core)

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        trimmed = line.strip()
        if trimmed.startswith("|"):
            trimmed = trimmed[1:]
        if trimmed.endswith("|"):
            trimmed = trimmed[:-1]
        return [cell.strip() for cell in trimmed.split("|")]

    @staticmethod
    def _pad_row(row: list[str], target_len: int) -> list[str]:
        if len(row) >= target_len:
            return row[:target_len]
        return row + [""] * (target_len - len(row))

    @staticmethod
    def _to_paragraph_markup(text: str) -> str:
        i = 0
        bold_on = False
        italic_on = False
        out: list[str] = []

        def push_char(ch: str) -> None:
            if ch == "&":
                out.append("&amp;")
                return
            if ch == "<":
                out.append("&lt;")
                return
            if ch == ">":
                out.append("&gt;")
                return
            out.append(ch)

        while i < len(text):
            ch = text[i]

            if ch == "\\" and i + 1 < len(text):
                push_char(text[i + 1])
                i += 2
                continue

            if text.startswith("**", i):
                out.append("</b>" if bold_on else "<b>")
                bold_on = not bold_on
                i += 2
                continue

            if ch == "*":
                out.append("</i>" if italic_on else "<i>")
                italic_on = not italic_on
                i += 1
                continue

            push_char(ch)
            i += 1

        if italic_on:
            out.append("</i>")
        if bold_on:
            out.append("</b>")

        return "".join(out)

    @staticmethod
    def _register_unicode_font() -> str:
        candidates = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/calibri.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        ]

        for path in candidates:
            if path.exists():
                font_name = f"TM_{path.stem}"
                try:
                    pdfmetrics.registerFont(TTFont(font_name, str(path)))
                    return font_name
                except Exception:
                    continue

        return "Helvetica"
