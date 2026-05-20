"""
scripts/sync_tests.py
=====================

Deterministic, dependency-free scaffolder that keeps ``tests/`` structurally
mirrored to ``src/transpiler_pro/``.

For every Python module under ``src/transpiler_pro/`` this script ensures a
matching pytest file exists under ``tests/`` with the same relative path
(see ``AGENTS.md`` for the full mirroring convention). When a mirror is
missing it scaffolds:

* a sub-package ``__init__.py`` (empty), and
* a ``test_<module>.py`` stub that
    - imports the source module (a passing import-smoke test), and
    - contains one ``xfail`` stub per public class/function discovered via
      ``ast``, so the human / Copilot agent has an obvious to-do list.

The script never overwrites an existing test file.

Usage
-----

    python scripts/sync_tests.py            # write missing stubs
    python scripts/sync_tests.py --check    # exit 1 if anything is missing
    python scripts/sync_tests.py --dry-run  # print actions, write nothing

This module uses only the Python standard library so it can run in any
environment (pre-commit, CI, fresh checkouts) without ``uv sync``.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "transpiler_pro"
TESTS_ROOT = REPO_ROOT / "tests"
PACKAGE_NAME = "transpiler_pro"


# --------------------------------------------------------------------------- #
# Path mapping
# --------------------------------------------------------------------------- #
def source_to_test_path(src_path: Path) -> Path:
    """Map a source ``.py`` path to its mirrored test path.

    Examples
    --------
    ``src/transpiler_pro/cli.py``                -> ``tests/test_cli.py``
    ``src/transpiler_pro/__init__.py``           -> ``tests/test_init.py``
    ``src/transpiler_pro/core/converter.py``     -> ``tests/core/test_converter.py``
    ``src/transpiler_pro/core/__init__.py``      -> ``tests/core/test_init.py``
    """
    rel = src_path.relative_to(SRC_ROOT)
    parts = list(rel.parts)
    stem = Path(parts[-1]).stem
    if stem == "__init__":
        filename = "test_init.py"
    else:
        filename = f"test_{stem}.py"
    return TESTS_ROOT.joinpath(*parts[:-1], filename)


def module_dotted_name(src_path: Path) -> str:
    """Return the dotted Python import path for a source file."""
    rel = src_path.relative_to(SRC_ROOT)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([PACKAGE_NAME, *parts]) if parts else PACKAGE_NAME


# --------------------------------------------------------------------------- #
# Source discovery
# --------------------------------------------------------------------------- #
def iter_source_modules() -> list[Path]:
    """Yield all ``*.py`` files under ``src/transpiler_pro/`` that should have
    a mirrored test, sorted for determinism.

    Private modules (leading underscore, other than ``__init__.py``) are
    skipped — see ``AGENTS.md`` section 6.
    """
    if not SRC_ROOT.exists():
        return []
    files: list[Path] = []
    for path in SRC_ROOT.rglob("*.py"):
        name = path.name
        if name.startswith("_") and name != "__init__.py":
            continue
        files.append(path)
    return sorted(files)


def public_symbols(src_path: Path) -> list[str]:
    """Return the names of public top-level classes and functions in ``src_path``.

    Uses ``ast`` so we never have to import (and therefore never have to
    resolve) the source module's heavyweight dependencies (spacy, typer, ...).
    Falls back to an empty list if the file can't be parsed.
    """
    try:
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []

    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names


# --------------------------------------------------------------------------- #
# Stub rendering
# --------------------------------------------------------------------------- #
def render_test_stub(src_path: Path) -> str:
    """Render the contents of a scaffolded ``test_<module>.py`` file."""
    dotted = module_dotted_name(src_path)
    symbols = public_symbols(src_path)
    rel_src = src_path.relative_to(REPO_ROOT).as_posix()
    rel_test = source_to_test_path(src_path).relative_to(REPO_ROOT).as_posix()
    test_func_suffix = "init" if src_path.stem == "__init__" else src_path.stem

    lines: list[str] = [
        '"""',
        f"Location: {rel_test}",
        "",
        f"Auto-scaffolded by scripts/sync_tests.py to mirror `{rel_src}`.",
        "",
        "These tests are stubs — replace the `xfail` markers with real",
        "assertions that exercise the corresponding source behavior. See",
        "AGENTS.md for the full mirroring and test-style conventions.",
        '"""',
        "",
        "import importlib",
        "",
        "import pytest",
        "",
        "",
        f"MODULE_NAME = {dotted!r}",
        "",
        "",
        f"def test_{test_func_suffix}_importable():",
        f'    """Smoke test: `{dotted}` imports without side effects."""',
        "    module = importlib.import_module(MODULE_NAME)",
        "    assert module is not None",
        "",
    ]

    for symbol in symbols:
        lines += [
            "",
            '@pytest.mark.xfail(reason="Auto-generated stub; replace with real assertions.", strict=False)',
            f"def test_{symbol}_smoke():",
            f'    """TODO: exercise `{dotted}.{symbol}` and assert on observable behavior."""',
            "    module = importlib.import_module(MODULE_NAME)",
            f"    assert hasattr(module, {symbol!r})",
            "",
        ]

    return "\n".join(lines).rstrip() + "\n"


def render_tests_init() -> str:
    """Empty ``__init__.py`` body for a tests sub-package."""
    return ""


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
class Action:
    """A single filesystem action the scaffolder would take."""

    def __init__(self, path: Path, content: str, kind: str) -> None:
        self.path = path
        self.content = content
        self.kind = kind  # "test" or "init"

    def rel(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def plan_actions() -> list[Action]:
    """Compute the set of files that need to be created to satisfy the mirror
    convention. Does not touch the filesystem."""
    actions: list[Action] = []
    seen_init_dirs: set[Path] = set()

    for src_path in iter_source_modules():
        test_path = source_to_test_path(src_path)

        # Ensure every parent directory of the test file has an __init__.py.
        for parent in _ancestors_within_tests(test_path.parent):
            if parent in seen_init_dirs:
                continue
            seen_init_dirs.add(parent)
            init_path = parent / "__init__.py"
            if not init_path.exists():
                actions.append(Action(init_path, render_tests_init(), kind="init"))

        if not test_path.exists():
            actions.append(Action(test_path, render_test_stub(src_path), kind="test"))

    return actions


def _ancestors_within_tests(path: Path) -> list[Path]:
    """Return every directory from ``TESTS_ROOT`` down to (and including)
    ``path``, in top-down order."""
    try:
        path.relative_to(TESTS_ROOT)
    except ValueError:
        return []
    result: list[Path] = []
    current = path
    while True:
        result.append(current)
        if current == TESTS_ROOT:
            break
        current = current.parent
    return list(reversed(result))


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
def apply_actions(actions: list[Action], dry_run: bool) -> None:
    for action in actions:
        verb = "[dry-run] would create" if dry_run else "created"
        print(f"{verb}: {action.rel()}")
        if dry_run:
            continue
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_text(action.content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror tests/ to src/transpiler_pro/ by scaffolding pytest stubs."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any test mirror is missing. Writes nothing.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing anything.",
    )
    args = parser.parse_args(argv)

    if not SRC_ROOT.exists():
        print(f"error: source root {SRC_ROOT} not found", file=sys.stderr)
        return 2

    actions = plan_actions()

    if args.check:
        if actions:
            print("Missing test mirrors:", file=sys.stderr)
            for action in actions:
                print(f"  - {action.rel()}", file=sys.stderr)
            print(
                "\nRun `python scripts/sync_tests.py` to scaffold them.",
                file=sys.stderr,
            )
            return 1
        print("All source modules have a mirrored test file.")
        return 0

    if not actions:
        print("Nothing to do — tests/ is already in sync with src/.")
        return 0

    apply_actions(actions, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
