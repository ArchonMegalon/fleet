#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import inspect
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Callable


ROOT = Path("/docker/fleet")
TEST_PATH = ROOT / "tests" / "test_materialize_weekly_governor_packet.py"
RUNNER_META_TEST_PREFIX = "test_run_next90_m106_weekly_governor_packet_tests_"
DEFAULT_TEST_TIMEOUT_SECONDS = max(
    1, int(os.environ.get("NEXT90_M106_TEST_TIMEOUT_SECONDS", "30"))
)


def _load_test_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_test_functions(
    module, *, include_runner_meta_tests: bool = False
) -> list[tuple[str, Callable[..., object]]]:
    functions: list[tuple[str, Callable[..., object]]] = []
    for name, value in vars(module).items():
        if (
            name.startswith("test_")
            and (include_runner_meta_tests or not name.startswith(RUNNER_META_TEST_PREFIX))
            and inspect.isfunction(value)
            and value.__module__ == module.__name__
        ):
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


def _run_single_test_by_name(name: str, tmp_root: Path) -> int:
    module = _load_test_module(TEST_PATH)
    test_map = {
        test_name: function
        for test_name, function in _iter_test_functions(
            module,
            include_runner_meta_tests=True,
        )
    }
    function = test_map.get(name)
    if function is None:
        print(f"unknown test function: {name}", file=sys.stderr)
        return 1
    try:
        _call_test(name, function, tmp_root)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


def _run_test_in_subprocess(name: str, tmp_root: Path, timeout_seconds: int) -> tuple[bool, str]:
    child_tmp_root = tmp_root / name
    child_tmp_root.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--run-test",
        name,
        "--tmp-root",
        str(child_tmp_root),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, f"{name} timed out after {timeout_seconds}s"
    if result.returncode == 0:
        return True, ""
    details = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part.strip()
    )
    return False, details or f"{name} exited with code {result.returncode}"


def _parse_args() -> argparse.Namespace:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Next90 M106 weekly governor packet fixture tests."
    )
    parser.add_argument(
        "--run-test",
        help="internal: run a single named test function in isolation",
    )
    parser.add_argument(
        "--tmp-root",
        help="temporary root directory for a single isolated test run",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TEST_TIMEOUT_SECONDS,
        help="per-test timeout for isolated direct-runner execution",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help="run each collected test in its own subprocess instead of in-process",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.run_test:
        if not args.tmp_root:
            print("--tmp-root is required with --run-test", file=sys.stderr)
            return 1
        return _run_single_test_by_name(args.run_test, Path(args.tmp_root))

    module = _load_test_module(TEST_PATH)
    tests = _iter_test_functions(module)
    if not tests:
        print(f"no test functions found in {TEST_PATH}", file=sys.stderr)
        return 1

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="next90-m106-governor-tests-") as temp_dir:
        tmp_root = Path(temp_dir)
        for name, function in tests:
            if args.isolate:
                ok, details = _run_test_in_subprocess(name, tmp_root, args.timeout_seconds)
                if not ok:
                    failures.append(name)
                    if details:
                        print(details, file=sys.stderr)
                continue
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
