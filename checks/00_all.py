from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from util.common import CHECK_FAIL, CHECK_OK, CHECK_WARN


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    script_name: str
    status: str
    exit_code: int | None


def discover_check_scripts(checks_dir: Path, *, current_file: Path) -> list[Path]:
    candidates = sorted(checks_dir.glob("*.py"), key=lambda p: p.name.lower())
    return [p for p in candidates if p.is_file() and p.name != current_file.name and not p.name.startswith("_")]


def import_module_from_path(module_path: Path) -> Any:
    module_name = f"_check_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot create module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def suppress_output(func, /, *args, **kwargs):
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        return func(*args, **kwargs)


def run_check_script(script_path: Path) -> CheckOutcome:
    try:
        module = import_module_from_path(script_path)
    except Exception:
        return CheckOutcome(script_name=script_path.name, status=CHECK_FAIL, exit_code=1)

    run_func = getattr(module, "run", None)
    if run_func is None or not callable(run_func):
        return CheckOutcome(script_name=script_path.name, status=CHECK_WARN, exit_code=None)

    try:
        exit_code = suppress_output(run_func)
    except Exception:
        return CheckOutcome(script_name=script_path.name, status=CHECK_FAIL, exit_code=1)

    if exit_code == 0:
        return CheckOutcome(script_name=script_path.name, status=CHECK_OK, exit_code=0)

    return CheckOutcome(
        script_name=script_path.name,
        status=CHECK_FAIL,
        exit_code=int(exit_code) if isinstance(exit_code, int) else 1,
    )


def main() -> int:
    current_file = Path(__file__).resolve()
    checks_dir = current_file.parent

    if str(checks_dir) not in sys.path:
        sys.path.insert(0, str(checks_dir))

    scripts = discover_check_scripts(checks_dir, current_file=current_file)
    if not scripts:
        print(f"{CHECK_OK} no checks discovered")
        return 0

    outcomes = [run_check_script(p) for p in scripts]

    for outcome in outcomes:
        print(f"{outcome.status} {outcome.script_name}")

    failures = [o for o in outcomes if o.status == CHECK_FAIL]
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
