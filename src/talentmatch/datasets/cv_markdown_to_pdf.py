from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


@dataclass(frozen=True)
class StoreCvPdfResult:
    """Result of storing CV Markdown as a PDF file."""
    uuid: str


class CvMarkdownPdfStore:
    """Stores a CV Markdown as a PDF file under a UUID-based name."""

    def __init__(self, settings: Any) -> None:
        self._base_dir = Path(settings.paths.cv_pdf_dir)
        self._font_name = self._register_unicode_font()

    def store(self, uuid: str, markdown: str) -> StoreCvPdfResult:
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

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=f"{uuid}",
        )

        story = list(self._markdown_to_flowables(markdown, base_style, heading_1, heading_2))
        doc.build(story)

        return StoreCvPdfResult(uuid=uuid)

    def _markdown_to_flowables(
            self,
            markdown: str,
            base_style: ParagraphStyle,
            heading_1: ParagraphStyle,
            heading_2: ParagraphStyle,
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

        for raw in lines:
            line = raw.strip()

            if not line:
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                continue

            if line.startswith("# "):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                yield Paragraph(self._to_paragraph_markup(line[2:].strip()), heading_1)
                yield Spacer(1, 8)
                continue

            if line.startswith("## "):
                for f in flush_bullets():
                    yield f
                for f in flush_paragraph():
                    yield f
                yield Paragraph(self._to_paragraph_markup(line[3:].strip()), heading_2)
                yield Spacer(1, 6)
                continue

            if line.startswith(("- ", "* ")):
                for f in flush_paragraph():
                    yield f
                bullet_lines.append(line[2:].strip())
                continue

            paragraph_lines.append(line)

        for f in flush_bullets():
            yield f
        for f in flush_paragraph():
            yield f

    @staticmethod
    def _to_paragraph_markup(text: str) -> str:
        """Convert a minimal subset of Markdown inline emphasis to ReportLab paragraph markup."""
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
