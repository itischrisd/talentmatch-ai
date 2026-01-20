from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from talentmatch.generation import generate_dataset, generate_single_rfp
from util.common import assert_true, build_check_context, print_fail, print_ok


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def resolve_fragment_paths(settings_entry_path: Path) -> dict[str, Path]:
    entry = read_toml(settings_entry_path)
    settings_meta = entry.get("settings", {})
    includes = settings_meta.get("includes", []) if isinstance(settings_meta, dict) else []
    include_paths = [(settings_entry_path.parent / str(p)).resolve() for p in includes]

    by_name: dict[str, Path] = {}
    for p in include_paths:
        name = p.name.lower()
        if name.endswith("llm.toml"):
            by_name["llm"] = p
        if name.endswith("datasets.toml"):
            by_name["datasets"] = p

    if "llm" in by_name and "datasets" in by_name:
        return by_name

    for p in include_paths:
        data = read_toml(p)
        if "llm" in data:
            by_name.setdefault("llm", p)
        if "datasets" in data:
            by_name.setdefault("datasets", p)

    return by_name


def write_override_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def run() -> int:
    context = build_check_context(Path(__file__))

    if not context.prompts_path.exists():
        print_fail(f'Prompts TOML not found: "{context.prompts_path}"')
        return 1
    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return 1

    settings_path = context.repo_root / "configs" / "settings.toml"

    try:
        import talentmatch.generation as generation_module

        exported = set(getattr(generation_module, "__all__", []))
        required = {"generate_dataset", "generate_single_rfp"}
        ok = assert_true(required.issubset(exported), ok="generation public API __all__ ok",
                         fail="generation __all__ missing items")
        if not ok:
            return 1
    except Exception as exc:
        print_fail(f"generation module public API check failed: {exc}")
        return 1

    try:
        single = generate_single_rfp(
            settings_toml_path=str(settings_path),
            prompts_toml_path=str(context.prompts_path),
        )
        print_ok("generate_single_rfp() succeeded")
        print("Located single RFP PDF at:", single.get("pdf_file", ""))
    except Exception as exc:
        print_fail(f"generate_single_rfp() failed: {exc}")
        return 1

    failures = 0

    failures += 0 if assert_true(isinstance(single, dict), ok="single_rfp result is dict",
                                 fail="single_rfp result is not dict") else 1
    failures += 0 if assert_true(bool(single.get("markdown", "").strip()), ok="single_rfp markdown non-empty",
                                 fail="single_rfp markdown empty") else 1

    pdf_file = Path(str(single.get("pdf_file", "")))
    failures += 0 if assert_true(pdf_file.exists(), ok="single_rfp pdf exists",
                                 fail=f'single_rfp pdf not found: "{pdf_file}"') else 1
    if pdf_file.exists():
        failures += 0 if assert_true(pdf_file.stat().st_size > 0, ok="single_rfp pdf non-empty",
                                     fail="single_rfp pdf empty") else 1

    try:
        dataset = generate_dataset(
            settings_toml_path=str(settings_path),
            prompts_toml_path=str(context.prompts_path),
        )
        print_ok("generate_dataset() succeeded")
    except Exception as exc:
        print_fail(f"generate_dataset() failed: {exc}")
        return 1

    failures += 0 if assert_true(isinstance(dataset, dict), ok="dataset result is dict",
                                 fail="dataset result is not dict") else 1

    profiles = dataset.get("profiles", [])
    projects = dataset.get("projects", [])
    rfps = dataset.get("rfps", [])
    cv_files = dataset.get("cv_files", [])
    rfp_files = dataset.get("rfp_files", [])

    failures += 0 if assert_true(len(profiles) == 2, ok="dataset generated 2 profile",
                                 fail=f"expected 2 profile, got {len(profiles)}") else 1
    failures += 0 if assert_true(len(projects) == 2, ok="dataset generated 2 project",
                                 fail=f"expected 2 project, got {len(projects)}") else 1
    failures += 0 if assert_true(len(rfps) == 2, ok="dataset generated 2 rfp",
                                 fail=f"expected 2 rfp, got {len(rfps)}") else 1
    failures += 0 if assert_true(len(cv_files) == 2, ok="dataset produced 2 cv pdf path",
                                 fail=f"expected 2 cv pdf path, got {len(cv_files)}") else 1
    failures += 0 if assert_true(len(rfp_files) == 2, ok="dataset produced 2 rfp pdf path",
                                 fail=f"expected 2 rfp pdf path, got {len(rfp_files)}") else 1

    for label, path_str in [("profiles_file", dataset.get("profiles_file")),
                            ("projects_file", dataset.get("projects_file")),
                            ("rfps_file", dataset.get("rfps_file"))]:
        p = Path(str(path_str or ""))
        failures += 0 if assert_true(p.exists(), ok=f"{label} exists", fail=f'{label} missing: "{p}"') else 1
        if p.exists():
            failures += 0 if assert_true(p.stat().st_size > 0, ok=f"{label} non-empty",
                                         fail=f"{label} empty") else 1

    for label, file_list in [("cv_files", cv_files), ("rfp_files", rfp_files)]:
        for idx, file_path in enumerate(file_list, start=1):
            p = Path(str(file_path))
            failures += 0 if assert_true(p.exists(), ok=f"{label}[{idx}] exists",
                                         fail=f'{label}[{idx}] missing: "{p}"') else 1
            if p.exists():
                failures += 0 if assert_true(p.stat().st_size > 0, ok=f"{label}[{idx}] non-empty",
                                             fail=f"{label}[{idx}] empty") else 1

    if failures == 0:
        print_ok("Generation module checks passed")
        return 0

    print_fail(f"Generation module checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
