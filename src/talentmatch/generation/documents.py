from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.flowables import HRFlowable

from talentmatch.config.prompts_models import Prompts


class _Invokable(Protocol):
    def invoke(self, prompt: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class _PdfTheme:
    base_font_name: str
    base_font_size: int
    leading_multiplier: float
    body_margin_pt: float
    body_padding_pt: float
    max_width_pt: float | None
    h1_color: colors.Color
    h1_border_color: colors.Color
    h1_border_width_pt: float
    h2_color: colors.Color
    h2_space_before_pt: float
    h3_color: colors.Color
    strong_color: colors.Color
    ul_left_indent_pt: float

    @classmethod
    def from_css(cls, css: str) -> _PdfTheme:
        """
        Parse a limited CSS subset used by the project and map it to ReportLab styling primitives.
        :param css: CSS string from configuration
        :return: theme instance
        """

        body = _Css.select(css, "body")
        h1 = _Css.select(css, "h1")
        h2 = _Css.select(css, "h2")
        h3 = _Css.select(css, "h3")
        strong = _Css.select(css, "strong")
        ul = _Css.select(css, "ul")

        font_family = _Css.prop(body, "font-family") or "Helvetica"
        base_font_name = "Helvetica" if "arial" in font_family.lower() else "Helvetica"

        leading_multiplier = _Css.number(_Css.prop(body, "line-height"), default=1.4)
        body_margin_px = _Css.px_first(_Css.prop(body, "margin"), default_px=40)
        body_padding_px = _Css.px(_Css.prop(body, "padding"), default_px=20)
        max_width_px = _Css.px(_Css.prop(body, "max-width"), default_px=None)

        h1_color = _Css.color(_Css.prop(h1, "color"), default="#2c3e50")
        border_bottom = _Css.prop(h1, "border-bottom") or ""
        border_width_px, border_color_hex = _Css.border_bottom(border_bottom, default_width_px=2,
                                                               default_color="#3498db")
        h2_color = _Css.color(_Css.prop(h2, "color"), default="#34495e")
        h2_space_before_px = _Css.px(_Css.prop(h2, "margin-top"), default_px=30)
        h3_color = _Css.color(_Css.prop(h3, "color"), default="#7f8c8d")
        strong_color = _Css.color(_Css.prop(strong, "color"), default="#2c3e50")
        ul_indent_px = _Css.px(_Css.prop(ul, "margin-left"), default_px=20)

        return cls(
            base_font_name=base_font_name,
            base_font_size=11,
            leading_multiplier=float(leading_multiplier),
            body_margin_pt=_Css.px_to_pt(body_margin_px),
            body_padding_pt=_Css.px_to_pt(body_padding_px),
            max_width_pt=_Css.px_to_pt(max_width_px) if max_width_px is not None else None,
            h1_color=h1_color,
            h1_border_color=_Css.color(border_color_hex, default="#3498db"),
            h1_border_width_pt=_Css.px_to_pt(border_width_px),
            h2_color=h2_color,
            h2_space_before_pt=_Css.px_to_pt(h2_space_before_px),
            h3_color=h3_color,
            strong_color=strong_color,
            ul_left_indent_pt=_Css.px_to_pt(ul_indent_px),
        )

    def page_margins_pt(self) -> tuple[float, float, float, float]:
        """
        Compute page margins approximating the former body margin + padding + max-width centering.
        :return: (left, right, top, bottom) margins in points
        """

        page_width, _page_height = A4
        base_lr = float(self.body_margin_pt + self.body_padding_pt)
        available_width = float(page_width - (2 * base_lr))

        left = right = base_lr
        if self.max_width_pt is not None and 0 < self.max_width_pt < available_width:
            extra = float((available_width - self.max_width_pt) / 2)
            left = right = base_lr + extra

        top = bottom = float(self.body_margin_pt + self.body_padding_pt)
        return left, right, top, bottom


class _Css:
    _BLOCK_RE = re.compile(r"(?P<selector>[^{]+)\{(?P<body>[^}]*)}", flags=re.DOTALL)
    _PROP_RE = re.compile(r"(?P<name>[-a-zA-Z]+)\s*:\s*(?P<value>[^;]+)\s*;", flags=re.DOTALL)
    _HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
    _PX_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*px\b")
    _NUM_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\b")

    @classmethod
    def select(cls, css: str, selector: str) -> str:
        """
        Extract a selector block.
        :param css: full CSS
        :param selector: selector name (e.g. body, h1)
        :return: block body or empty string
        """

        selector_norm = selector.strip().lower()
        for match in cls._BLOCK_RE.finditer(css):
            found = match.group("selector").strip().lower()
            if found == selector_norm:
                return match.group("body")
        return ""

    @classmethod
    def prop(cls, block: str, name: str) -> str | None:
        """
        Extract a property value from a selector block.
        :param block: selector block body
        :param name: property name
        :return: property value or None
        """

        name_norm = name.strip().lower()
        for match in cls._PROP_RE.finditer(block):
            if match.group("name").strip().lower() == name_norm:
                return match.group("value").strip()
        return None

    @classmethod
    def px(cls, value: str | None, *, default_px: float | None) -> float | None:
        """
        Parse a single pixel value.
        :param value: raw css value
        :param default_px: default when not present
        :return: pixel value or default
        """

        if not value:
            return default_px
        match = cls._PX_RE.search(value)
        if match is None:
            return default_px
        return float(match.group("num"))

    @classmethod
    def px_first(cls, value: str | None, *, default_px: float) -> float:
        """
        Parse the first pixel value (useful for shorthand properties like margin).
        :param value: raw CSS value
        :param default_px: fallback
        :return: pixel value
        """

        parsed = cls.px(value, default_px=None)
        return float(default_px) if parsed is None else float(parsed)

    @classmethod
    def number(cls, value: str | None, *, default: float) -> float:
        """
        Parse a generic number.
        :param value: raw value
        :param default: fallback
        :return: parsed number
        """

        if not value:
            return float(default)
        match = cls._NUM_RE.search(value)
        if match is None:
            return float(default)
        return float(match.group("num"))

    @classmethod
    def color(cls, value: str | None, *, default: str) -> colors.Color:
        """
        Parse a hex color.
        :param value: raw value
        :param default: fallback
        :return: ReportLab color
        """

        raw = value or default
        match = cls._HEX_RE.search(raw)
        return colors.HexColor(match.group(0) if match else default)

    @classmethod
    def border_bottom(cls, value: str, *, default_width_px: float, default_color: str) -> tuple[float, str]:
        """
        Parse a 'border-bottom' declaration like '2px solid #3498db'.
        :param value: raw declaration
        :param default_width_px: fallback width in px
        :param default_color: fallback color
        :return: (width_px, color_hex)
        """

        width = cls.px(value, default_px=default_width_px) or float(default_width_px)
        match = cls._HEX_RE.search(value)
        return float(width), match.group(0) if match else default_color

    @staticmethod
    def px_to_pt(px: float) -> float:
        """
        Convert CSS pixels (96 DPI) to points.
        :param px: pixels
        :return: points
        """

        return float(px) * 0.75


class _MarkupParser:
    _HEADING_RE = re.compile(r"^\s*(?P<level>#{1,6})\s+(?P<text>.+?)\s*$")
    _BULLET_RE = re.compile(r"^\s*[-*•]\s+(?P<text>.+?)\s*$")
    _ORDERED_RE = re.compile(r"^\s*(?P<num>\d+)\.\s+(?P<text>.+?)\s*$")
    _HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,})\s*$")
    _INDENT_RE = re.compile(r"^\s{2,}(?P<text>\S.+?)\s*$")

    def __init__(self, *, theme: _PdfTheme) -> None:
        self._theme = theme
        self._styles = self._build_styles(theme)

    def build_flowables(self, source: str) -> list:
        """
        Convert lightweight Markdown into ReportLab flowables
        :param source: markdown-like content
        :return: flowables for document building
        """

        lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        flowables: list = []
        idx = 0

        while idx < len(lines):
            line = lines[idx].rstrip()

            if not line.strip():
                idx += 1
                continue

            if self._HR_RE.fullmatch(line):
                flowables.append(HRFlowable(width="100%", thickness=1))
                flowables.append(Spacer(1, self._styles["body"].leading * 0.6))
                idx += 1
                continue

            heading = self._HEADING_RE.match(line)
            if heading:
                level = len(heading.group("level"))
                text = heading.group("text")
                style_key = "h3" if level >= 3 else "h2" if level == 2 else "h1"
                flowables.append(Paragraph(self._to_paragraph_markup(text), self._styles[style_key]))
                idx += 1
                continue

            bullet = self._BULLET_RE.match(line)
            ordered = self._ORDERED_RE.match(line)
            if bullet or ordered:
                list_items: list[str] = []
                while idx < len(lines):
                    current = lines[idx].rstrip()
                    bullet_match = self._BULLET_RE.match(current)
                    ordered_match = self._ORDERED_RE.match(current)

                    if bullet_match:
                        item_text, idx = self._consume_list_item(lines, idx, bullet_match.group("text"))
                        list_items.append(item_text)
                        continue

                    if ordered_match:
                        item_text, idx = self._consume_list_item(lines, idx, ordered_match.group("text"))
                        list_items.append(item_text)
                        continue

                    break

                flowables.append(self._list_flowable(list_items))
                flowables.append(Spacer(1, self._styles["body"].leading * 0.6))
                continue

            paragraph_lines: list[str] = []
            while idx < len(lines):
                current = lines[idx].rstrip()
                if not current.strip():
                    idx += 1
                    break
                if self._HEADING_RE.match(current) or self._BULLET_RE.match(current) or self._ORDERED_RE.match(current):
                    break
                if self._HR_RE.fullmatch(current):
                    break
                paragraph_lines.append(current.strip())
                idx += 1

            paragraph_text = " ".join(paragraph_lines).strip()
            if paragraph_text:
                flowables.append(Paragraph(self._to_paragraph_markup(paragraph_text), self._styles["body"]))

        if not flowables:
            flowables.append(Paragraph("", self._styles["body"]))
        return flowables

    def _consume_list_item(self, lines: list[str], start_idx: int, initial_text: str) -> tuple[str, int]:
        text_parts: list[str] = [initial_text.strip()]
        idx = start_idx + 1

        while idx < len(lines):
            candidate = lines[idx].rstrip()
            if not candidate.strip():
                idx += 1
                break

            if self._BULLET_RE.match(candidate) or self._ORDERED_RE.match(candidate) or self._HEADING_RE.match(
                    candidate):
                break

            indented = self._INDENT_RE.match(candidate)
            if indented:
                text_parts.append(indented.group("text").strip())
                idx += 1
                continue

            break

        return " ".join(text_parts).strip(), idx

    def _list_flowable(self, items: list[str]) -> ListFlowable:
        paragraphs = [
            ListItem(Paragraph(self._to_paragraph_markup(item), self._styles["list_item"])) for item in items if item
        ]

        return ListFlowable(
            paragraphs,
            leftIndent=float(self._theme.ul_left_indent_pt),
            bulletType="bullet"
        )

    def _to_paragraph_markup(self, text: str) -> str:
        escaped = xml_escape(text, {"'": "&#39;"})
        escaped = self._apply_inline_code(escaped)
        escaped = self._apply_bold(escaped)
        escaped = self._apply_italic(escaped)
        return escaped

    @staticmethod
    def _apply_inline_code(text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            inner = match.group(1)
            return f'<font face="Courier">{inner}</font>'

        return re.sub(r"`([^`]+)`", repl, text)

    def _apply_bold(self, text: str) -> str:
        color = self._theme.strong_color.hexval()

        def repl(match: re.Match[str]) -> str:
            inner = match.group(1)
            return f'<b><font color="{color}">{inner}</font></b>'

        text = re.sub(r"\*\*(.+?)\*\*", repl, text)
        return re.sub(r"__(.+?)__", repl, text)

    @staticmethod
    def _apply_italic(text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            return f"<i>{match.group(1)}</i>"

        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", repl, text)
        return re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", repl, text)

    @staticmethod
    def _build_styles(theme: _PdfTheme) -> dict[str, ParagraphStyle]:
        base_leading = float(theme.base_font_size) * float(theme.leading_multiplier)

        body = ParagraphStyle(
            name="Body",
            fontName=theme.base_font_name,
            fontSize=float(theme.base_font_size),
            leading=base_leading,
            spaceAfter=base_leading * 0.35,
        )

        h1 = ParagraphStyle(
            name="H1",
            parent=body,
            fontSize=float(theme.base_font_size) + 8,
            leading=(float(theme.base_font_size) + 8) * 1.2,
            textColor=theme.h1_color,
            spaceBefore=0,
            spaceAfter=base_leading * 0.55,
            borderColor=theme.h1_border_color,
            borderBottomWidth=float(theme.h1_border_width_pt),
            borderPadding=base_leading * 0.15,
            keepWithNext=True,
        )

        h2 = ParagraphStyle(
            name="H2",
            parent=body,
            fontSize=float(theme.base_font_size) + 3,
            leading=(float(theme.base_font_size) + 3) * 1.25,
            textColor=theme.h2_color,
            spaceBefore=float(theme.h2_space_before_pt),
            spaceAfter=base_leading * 0.45,
            keepWithNext=True,
        )

        h3 = ParagraphStyle(
            name="H3",
            parent=body,
            fontSize=float(theme.base_font_size) + 1,
            leading=(float(theme.base_font_size) + 1) * 1.2,
            textColor=theme.h3_color,
            spaceBefore=base_leading * 0.5,
            spaceAfter=base_leading * 0.35,
            keepWithNext=True,
        )

        list_item = ParagraphStyle(
            name="ListItem",
            parent=body,
            spaceAfter=base_leading * 0.2,
        )

        return {"body": body, "h1": h1, "h2": h2, "h3": h3, "list_item": list_item}


class DocumentService:
    """
    Renders CVs and RFPs using an LLM and converts lightweight Markdown into PDFs via ReportLab.
    """

    def __init__(
            self,
            *,
            prompts: Prompts,
            proficiency_levels: list[str],
            pdf_css: str,
            cv_llm: _Invokable,
            rfp_llm: _Invokable,
    ) -> None:
        self._prompts = prompts
        self._proficiency_levels = proficiency_levels
        self._cv_llm = cv_llm
        self._rfp_llm = rfp_llm
        self._theme = _PdfTheme.from_css(pdf_css)
        self._parser = _MarkupParser(theme=self._theme)

    def render_cv_markdown(self, profile: dict) -> str:
        """
        Render CV Markdown using the configured template.
        :param profile: programmer profile data
        :return: string of rendered CV in Markdown
        """

        skills_text = ", ".join(f"{s.get('name')} ({s.get('proficiency')})" for s in profile.get("skills", []))
        projects_text = ", ".join(profile.get("projects", []))
        certs_text = ", ".join(profile.get("certifications", []))

        template = self._prompts.datasets.cv_markdown
        prompt = template.format(
            name=profile.get("name", ""),
            email=profile.get("email", ""),
            location=profile.get("location", ""),
            skills=skills_text,
            projects=projects_text,
            certifications=certs_text,
            proficiency_levels=", ".join(self._proficiency_levels),
        )
        return self._invoke_llm_document(self._cv_llm, prompt, empty_error="LLM returned empty content for CV")

    def render_rfp_markdown(self, rfp: dict) -> str:
        """
        Render RFP Markdown using the configured template.
        :param rfp: RFP data
        :return: string of rendered RFP in Markdown
        """

        required_label = self._prompts.datasets.requirement_labels.required
        preferred_label = self._prompts.datasets.requirement_labels.preferred

        lines: list[str] = []
        for req in rfp.get("requirements", []):
            label = required_label if req.get("is_mandatory") else preferred_label
            certs = req.get("preferred_certifications") or []
            cert_text = f" (Preferred certifications: {', '.join(certs)})" if certs else ""
            lines.append(f"- {label}: {req.get('skill_name')} - {req.get('min_proficiency')} level{cert_text}")

        remote = (
            self._prompts.datasets.remote_work_labels.allowed
            if rfp.get("remote_allowed")
            else self._prompts.datasets.remote_work_labels.not_allowed
        )

        template = self._prompts.datasets.rfp_markdown
        prompt = template.format(
            title=rfp.get("title", ""),
            client=rfp.get("client", ""),
            project_type=rfp.get("project_type", ""),
            description=rfp.get("description", ""),
            duration_months=rfp.get("duration_months", ""),
            team_size=rfp.get("team_size", ""),
            budget_range=rfp.get("budget_range", ""),
            start_date=rfp.get("start_date", ""),
            location=rfp.get("location", ""),
            remote_work=remote,
            requirements="\n".join(lines),
        )
        return self._invoke_llm_document(self._rfp_llm, prompt, empty_error="LLM returned empty content for RFP")

    def write_markdown_pdf(self, markdown_content: str, *, filename: str, output_dir: Path) -> Path:
        """
        Convert Markdown-like content to PDF and return the resulting file path.
        :param markdown_content: content in Markdown format
        :param filename: name of the output PDF file (without extension)
        :param output_dir: directory to write the PDF file to
        :return: path to the resulting PDF file
        """

        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / f"{filename}.pdf"

        left, right, top, bottom = self._theme.page_margins_pt()
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=float(left),
            rightMargin=float(right),
            topMargin=float(top),
            bottomMargin=float(bottom),
            title=str(filename),
        )

        flowables = self._parser.build_flowables(markdown_content)
        doc.build(flowables)
        return pdf_path

    def _invoke_llm_document(self, llm: _Invokable, prompt: str, *, empty_error: str) -> str:
        response = llm.invoke(prompt)
        content = str(getattr(response, "content", ""))
        cleaned = self._strip_fenced_code_blocks(content).strip()
        if not cleaned:
            raise ValueError(empty_error)
        return cleaned

    @staticmethod
    def _strip_fenced_code_blocks(text: str) -> str:
        stripped = text.strip()
        wrapped = re.fullmatch(r"```[^\n]*\n(?P<body>.*)\n```", stripped, flags=re.DOTALL)
        if wrapped:
            return wrapped.group("body")
        return re.sub(r"^\s*```[^\n]*\s*$", "", stripped, flags=re.MULTILINE).strip()
