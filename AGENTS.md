# AGENTS.md — Test-Sync Agent Instructions

This file is the canonical instruction set for any automated agent (GitHub
Copilot coding agent, local LLM-based helper, etc.) that maintains the test
suite in this repository. It is also a useful reference for human contributors.

The agent's job, in one sentence: **keep `tests/` structurally mirrored to
`src/transpiler_pro/`, and write/refresh pytest tests when source code
changes.**

---

## 1. Mirroring convention (hard rule)

For every Python module under `src/transpiler_pro/`, there must exist a
matching test file under `tests/` with the same relative path.

| Source path                                       | Test path                                  |
|---------------------------------------------------|--------------------------------------------|
| `src/transpiler_pro/__init__.py`                  | `tests/test_init.py`                       |
| `src/transpiler_pro/cli.py`                       | `tests/test_cli.py`                        |
| `src/transpiler_pro/<subpkg>/__init__.py`         | `tests/<subpkg>/test_init.py` *(optional)* |
| `src/transpiler_pro/<subpkg>/<module>.py`         | `tests/<subpkg>/test_<module>.py`          |
| `src/transpiler_pro/<a>/<b>/<module>.py`          | `tests/<a>/<b>/test_<module>.py`           |

Additional rules:

- Every test sub-directory must contain an `__init__.py` (matching the existing
  `tests/__init__.py` convention).
- Private modules (`_name.py`) are exercised indirectly through their public
  callers; do not create a dedicated test file for them unless they expose
  non-trivial logic.
- `src/transpiler_pro/<pkg>/__init__.py` files that only re-export do not need
  a dedicated test file.

A deterministic enforcer of this rule lives at `scripts/sync_tests.py` — see
section 5.

---

## 2. Test style guidelines

Tests in this repo use **pytest** (not `unittest`). Follow these conventions
when generating or updating tests:

- Use plain functions named `test_<behavior>()`. No `unittest.TestCase`
  classes.
- Prefer pytest fixtures (`tmp_path`, `monkeypatch`, `capsys`) over manual
  setup/teardown.
- Group related fixtures at the top of the file. Reuse fixtures across tests
  in the same module.
- Use `pytest.mark.parametrize` for table-driven cases.
- Use `pytest.raises` for expected exceptions.

### Mocking external side effects

The codebase imports heavy or network-bound libraries — mock them at the
boundary, never call the real thing in unit tests:

- **`typer` / CLI entry points** → use `typer.testing.CliRunner` and
  `monkeypatch` to swap pipeline functions. See `tests/test_cli.py` for the
  canonical pattern.
- **`spacy`** → mock `spacy.load` and any `nlp(...)` calls. Tests must not
  download or load the real `en_core_web_sm` model.
- **`requests`** → patch `requests.get` / `requests.post`. No real HTTP.
- **File system** → always write under `tmp_path`. Never write to repo paths.
- **`subprocess`** (e.g. for `vale`) → patch `subprocess.run` and assert on the
  arguments it was called with.

### Coverage

The repo runs `pytest --cov=src --cov-report=term-missing` via
`pyproject.toml`. New tests should actually exercise the code path they
target — a bare `import` smoke test is acceptable as a scaffold but should be
fleshed out with assertions on real behavior.

---

## 3. Update vs. delete policy

- **Add freely.** Missing test files for existing source modules are always
  fair game to create.
- **Update carefully.** When a source symbol's signature or behavior changes,
  update the corresponding test rather than rewriting it from scratch. Preserve
  existing fixtures and assertions where they still apply.
- **Never silently delete tests.** If a source symbol is removed, mark the
  obsolete test by:
  1. Adding `pytest.skip("Source symbol removed; needs review", allow_module_level=False)`
     at the top of the affected test function, **and**
  2. Leaving a `# TODO(test-sync): source X removed in <commit>` comment.

  A human reviewer makes the final call on deletion.

- **Never modify `src/`** during a test-sync run. The agent's write scope is
  restricted to `tests/**`, `scripts/sync_tests.py` outputs, and (if needed)
  `AGENTS.md` itself.

---

## 4. Pre-finalize checklist (agent must run these before opening/updating a PR)

1. `uv run python scripts/sync_tests.py --check` — fails if any source module
   is missing its mirror.
2. `uv run ruff check tests/` — lint generated tests.
3. `uv run pytest` — full suite must pass. If a generated stub fails because
   the agent encoded an incorrect expectation, fix the test rather than the
   source code.

If `uv` is unavailable in the agent's environment, use `python -m` equivalents
(`python -m pytest`, `python -m ruff`).

---

## 5. The `scripts/sync_tests.py` helper

A deterministic, dependency-free scaffolder lives at `scripts/sync_tests.py`.
It uses the standard library `ast` module to:

- Discover every `*.py` file under `src/transpiler_pro/`.
- Compute the expected mirror path under `tests/`.
- Create missing `tests/<subpkg>/__init__.py` files.
- Create missing `tests/.../test_<module>.py` stubs containing:
  - An import-smoke `test_<module>_importable()` test.
  - One `test_<symbol>_smoke()` stub (marked `xfail` with `strict=False`) per
    public class or function discovered via AST.

Modes:

```bash
python scripts/sync_tests.py            # write missing stubs
python scripts/sync_tests.py --check    # exit 1 if anything is missing (CI)
python scripts/sync_tests.py --dry-run  # print actions, write nothing
```

The script never overwrites an existing test file. It is safe to run on every
push and is what CI invokes.

---

## 6. Excluded / special-cased modules

- `src/transpiler_pro/cli.py` — already covered by `tests/test_cli.py` using
  `typer.testing.CliRunner`. The agent should keep that pattern when updating
  CLI tests, not switch to direct function calls.
- Anything under `src/transpiler_pro/**/_*.py` (leading underscore) — skip
  unless explicitly requested.
- Generated or vendored code (none today; add paths here as the project grows).

---

## 7. Where the agent gets invoked

`.github/workflows/sync_tests.yml` triggers on:

- `pull_request` events that touch `src/**`, and
- manual `workflow_dispatch`.

The workflow:

1. Runs `scripts/sync_tests.py --check` and fails fast if mirroring is broken.
2. On `workflow_dispatch`, also runs the scaffolder in write mode and opens a
   PR with the scaffolded stubs for a human (or downstream Copilot agent) to
   flesh out.

A human review is **always** required before merging auto-generated tests —
they can encode incorrect behavior as "expected".
