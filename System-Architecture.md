## 🏗 System Architecture & Module Interaction

The project follows a modular, "Smart Pipeline" architecture. It utilizes Natural Language Processing (NLP) and deterministic linting to not only convert documentation but proactively "heal" it.

### 🛰 Orchestration Layer

- **`cli.py`**: The central brain. It uses **Typer** to orchestrate the three-phase pipeline (Conversion -> Validation -> Repair).

### ⚙️ Core Transformation & Repair Layer

- **`core/converter.py`**: Handles structural conversion (Markdown to AsciiDoc). It ensures deterministic mapping of headers, code blocks, and lists.
- **`core/linter.py`**: The "Sensor"; it integrates the **Vale CLI** to identify style violations. It captures suggested replacements from Vale's rule parameters, enabling a zero-hardcoded fix strategy.
- **`core/fixer.py`**: The "Healer"; it uses **spaCy NLP** for context-aware grammar repairs (for example, subject-verb agreement for future tense) and surgically applies spelling corrections provided by the linter.
- **`core/refiner.py`**: The "Navigation Architect"; it parses JavaScript sidebar configurations (common in MDX projects) and transforms them into hierarchical, Antora-compliant nav.adoc files. It bridges the gap between dynamic JS navigation and static AsciiDoc cross-references.

### 🛠 Support Layer

- **`utils/paths.py`**: The project's "Internal GPS." It provides absolute path resolution for all modules.

## 🔄 Data Flow Pipeline

1. **Initialization**: User executes `uv run transpile run --fix`.
2. **Phase 1 (Conversion)**: `converter.py` transforms files from `data/inputs/` to `data/outputs/`.
3. **Phase 2 (Validation)**: `linter.py` runs Vale against output files, extracting both errors and their suggested "Gold" replacements.
4. **Phase 3 (Auto-Heal)**: `fixer.py` analyzes the findings. It uses dependency parsing to ensure grammatical correctness (e.g., "We are" vs "The system is") and overwrites violations with suggested fixes.

### Project Layout (Standard `src` Layout)

| Directory/File | Responsibility |
| --- | --- |
| `src/transpiler_pro/` | Main Python package source code. |
| `data/` | Persistent storage for inputs, outputs, and local assets. |
| `styles/` | SUSE Style Guide YAML rules used by Vale. |
| `tests/` | Pytest suite (includes NLP context validation). |
| `pyproject.toml` | Environment manifest (Pins Python 3.12 and spaCy dependencies). |