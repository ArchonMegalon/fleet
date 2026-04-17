#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import inspect
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Callable


ROOT = Path("/docker/fleet")
TEST_PATH = ROOT / "tests" / "test_materialize_weekly_governor_packet.py"


def _load_test_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_test_functions(module) -> list[tuple[str, Callable[..., object]]]:
    functions: list[tuple[str, Callable[..., object]]] = []
    for name, value in vars(module).items():
        if name.startswith("test_") and callable(value):
            functions.append((name, value))
    return sorted(functions)


def _call_test(name: str, function: Callable[..., object], tmp_root: Path) -> None:
    signature = inspect.signature(function)
    kwargs = {}
    for parameter in signature.parameters.values():
        if parameter.name == "tmp_path":
            kwargs[parameter.name] = tmp_root / name
            kwargs[parameter.name].mkdir(parents=True, exist_ok=True)
        else:
            raise RuntimeError(
                f"{name} requires unsupported fixture parameter {parameter.name!r}"
            )
    function(**kwargs)


def main() -> int:
    module = _load_test_module(TEST_PATH)
    tests = _iter_test_functions(module)
    if not tests:
        print(f"no test functions found in {TEST_PATH}", file=sys.stderr)
        return 1

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="next90-m106-governor-tests-") as temp_dir:
        tmp_root = Path(temp_dir)
        for name, function in tests:
            try:
                _call_test(name, function, tmp_root)
            except Exception:
                failures.append(name)
                traceback.print_exc()

    if failures:
        print(
            "direct M106 weekly governor packet fixture tests failed: "
            + ", ".join(failures),
            file=sys.stderr,
        )
        return 1

    print(f"direct M106 weekly governor packet fixture tests passed: {len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
