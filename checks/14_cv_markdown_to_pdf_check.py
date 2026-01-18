from __future__ import annotations

from pathlib import Path

from common import assert_true, build_check_context, is_uuid, load_settings_from_context, print_fail, print_ok
from talentmatch.datasets import CvMarkdownPdfStore


def run() -> int:
    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    try:
        store = CvMarkdownPdfStore(settings)
        print_ok("CvMarkdownPdfStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"CvMarkdownPdfStore(settings) failed: {exc}")
        return 1

    uuid = "11111111-1111-4111-8111-111111111111"
    markdown = "\n".join(
        [
            "# Jan Kowalski",
            "Senior Python Developer",
            "",
            "## Skills",
            "- Python",
            "- FastAPI",
            "- PostgreSQL",
            "",
            "## Summary",
            "Doświadczony inżynier oprogramowania z naciskiem na backend i dane.",
        ]
    )

    failures = 0
    base_dir = Path(settings.paths.cv_pdf_dir)
    pdf_path = base_dir / f"{uuid}.pdf"

    try:
        result = store.store(uuid, markdown)
        print_ok("store(uuid, markdown) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, markdown) failed: {exc}")
        return 1

    failures += 0 if assert_true(is_uuid(result.uuid), ok="result uuid format ok",
                                 fail=f"result uuid invalid: {result.uuid}") else 1
    failures += 0 if assert_true(pdf_path.exists(), ok="pdf file exists",
                                 fail=f'pdf file not found: "{pdf_path}"') else 1
    failures += 0 if assert_true(pdf_path.stat().st_size > 0, ok="pdf file non-empty",
                                 fail="pdf file is empty") else 1

    try:
        store.store(uuid, markdown)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(pdf_path.exists(), ok="pdf file still exists after overwrite",
                                 fail="pdf file missing after overwrite") else 1

    if failures == 0:
        print_ok("Markdown -> PDF checks passed")
        return 0

    print_fail(f"Markdown -> PDF checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
