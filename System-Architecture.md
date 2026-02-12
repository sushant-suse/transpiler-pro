## 🏗 System Architecture & Module Interaction

The project follows a modular pipeline architecture where the **Command-Line Interface (CLI)** orchestrates specialized core components to transform and validate documentation.

### 🛰 Orchestration Layer

* **`cli.py`**: The central brain of the application. It uses the **Typer** framework to parse user commands and manages the high-level workflow by initializing the `DocConverter` and `StyleLinter`.

### ⚙️ Core Transformation Layer

* **`core/converter.py`**: Responsible for the structural transformation of content. It reads Markdown/MDX files from `data/inputs/` and applies advanced regex-based conversion logic to produce SUSE-standard AsciiDoc files in `data/outputs/`.
* **`core/linter.py`**: Performs linguistic and stylistic validation. It integrates with the **Vale CLI** using the custom rules defined in `styles/suse-styles/` to identify style violations (for example, future tense usage, spelling errors) in the generated AsciiDoc.
* **`core/refiner.py`**: A utility module designed for post-processing adjustments to ensure the final output strictly adheres to Antora documentation structures.

### 🛠 Support Layer

* **`utils/paths.py`**: The source of truth for the project's directory structure. It defines the absolute paths for input, output, and style directories, ensuring that the components always know where to find and save data, regardless of where the script is executed.

## 🔄 Data Flow Pipeline

1. **Initialization**: User executes `uv run transpile run` via `cli.py`.
2. **Path Resolution**: `cli.py` queries `paths.py` to locate the source `.md` files in `data/inputs/`.
3. **Phase 1 (Conversion)**: `cli.py` passes the file paths to `converter.py`, which writes the structural AsciiDoc to `data/outputs/`.
4. **Phase 2 (Validation)**: `cli.py` triggers `linter.py`, which scans the new `.adoc` files against the `styles/` library and reports findings to the console.
5. **Phase 3 (Repair)**: (Upcoming) Findings from the linter are passed to the `StyleFixer` (to be created in Phase 2) for automated correction.

### Project Layout

| Directory/File | Responsibility |
| --- | --- |
| `src/transpiler_pro/` | Main Python package source code. |
| `data/` | Sandbox for raw inputs and converted outputs. |
| `styles/` | External SUSE Style Guide rules for Vale. |
| `tests/` | Pytest suite ensuring 100% logic reliability. |
| `docs/` | Auto-generated API documentation (GitHub Pages source). |
