from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cv_markdown_to_pdf import CvMarkdownPdfStore
from .cv_struct_generator import StructuredCvGenerator
from .cv_struct_to_json import CvStructJsonStore
from .cv_struct_to_markdown import CvStructMarkdownStore


@dataclass(frozen=True)
class GenerateCvArtifactsResult:
    """Result of generating full CV artifacts (JSON, Markdown, PDF) under a single UUID."""
    uuid: str


class CvArtifactsPipeline:
    """Generates a full set of CV artifacts from scratch and stores them under UUID-based filenames."""

    def __init__(
            self,
            settings: Any,
            *,
            generator: StructuredCvGenerator | None = None,
            json_store: CvStructJsonStore | None = None,
            markdown_store: CvStructMarkdownStore | None = None,
            pdf_store: CvMarkdownPdfStore | None = None,
    ) -> None:
        self._settings = settings
        self._errors = settings.datasets.cv.errors

        self._generator = generator or StructuredCvGenerator(settings)
        self._json_store = json_store or CvStructJsonStore(settings)
        self._markdown_store = markdown_store or CvStructMarkdownStore(settings)
        self._pdf_store = pdf_store or CvMarkdownPdfStore(settings)

        self._markdown_dir = Path(settings.paths.cv_markdown_dir)

    def generate_one(self) -> GenerateCvArtifactsResult:
        cv_result = self._generator.generate_one()
        uuid = cv_result.uuid

        self._json_store.store(uuid, cv_result.cv)
        self._markdown_store.store(uuid, cv_result.cv)

        markdown_path = self._markdown_dir / f"{uuid}.md"
        markdown = markdown_path.read_text(encoding="utf-8")

        self._pdf_store.store(uuid, markdown)

        return GenerateCvArtifactsResult(uuid=uuid)

    def generate_many(self, count: int) -> list[GenerateCvArtifactsResult]:
        if count <= 0:
            raise ValueError(self._errors.count_must_be_positive)
        return [self.generate_one() for _ in range(count)]
