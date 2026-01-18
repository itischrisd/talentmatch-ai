from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .rfp_markdown_to_pdf import RfpMarkdownPdfStore
from .rfp_struct_generator import StructuredRfpGenerator
from .rfp_struct_to_json import RfpStructJsonStore
from .rfp_struct_to_markdown import RfpStructMarkdownStore


@dataclass(frozen=True)
class GenerateRfpArtifactsResult:
    """Result of generating full RFP artifacts (JSON, Markdown, PDF) under a single UUID."""
    uuid: str


class RfpArtifactsPipeline:
    """Generates a full set of RFP artifacts from scratch and stores them under UUID-based filenames."""

    def __init__(
            self,
            settings: Any,
            *,
            generator: StructuredRfpGenerator | None = None,
            json_store: RfpStructJsonStore | None = None,
            markdown_store: RfpStructMarkdownStore | None = None,
            pdf_store: RfpMarkdownPdfStore | None = None,
    ) -> None:
        self._settings = settings
        self._errors = settings.datasets.rfp.errors

        self._generator = generator or StructuredRfpGenerator(settings)
        self._json_store = json_store or RfpStructJsonStore(settings)
        self._markdown_store = markdown_store or RfpStructMarkdownStore(settings)
        self._pdf_store = pdf_store or RfpMarkdownPdfStore(settings)

        self._markdown_dir = Path(settings.paths.rfp_markdown_dir)

    def generate_one(self) -> GenerateRfpArtifactsResult:
        rfp_result = self._generator.generate_one()
        uuid = rfp_result.uuid

        self._json_store.store(uuid, rfp_result.rfp_struct)
        self._markdown_store.store(uuid, rfp_result.rfp_struct)

        markdown_path = self._markdown_dir / f"{uuid}.md"
        markdown = markdown_path.read_text(encoding="utf-8")

        self._pdf_store.store(uuid, markdown)

        return GenerateRfpArtifactsResult(uuid=uuid)

    def generate_many(self, count: int) -> list[GenerateRfpArtifactsResult]:
        if count <= 0:
            raise ValueError(self._errors.count_must_be_positive)
        return [self.generate_one() for _ in range(count)]
