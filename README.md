# 🚀 Personal Transpiler-Pro

A high-fidelity documentation transpiler designed to convert **Markdown** into **Antora-compliant AsciiDoc**, specifically tailored for SUSE technical documentation standards.

## 📌 Project Overview

This project solves the "hallucination" and formatting breakage issues common in standard conversion tools (like Pandoc or kramdoc) when dealing with complex UI components like admonitions, collapsible blocks, and cross-references. It uses a **Three-Step Pipeline**:

1. **Pre-processing**: Shields complex Markdown components using unique text markers.
2. **Transpilation**: Utilizes `kramdoc` for standard element conversion (tables, headers, bold/italic).
3. **Post-processing**: Deterministically reconstructs protected components into perfect AsciiDoc syntax.

## 📂 Folder Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Main engine: Pre/Post-processing & kramdoc wrapper
│   │   ├── linter.py       # Vale integration for SUSE style checking
│   │   ├── navigator.py    # (Planned) Directory traversal logic
│   │   └── fixer.py        # (Next Phase) Deterministic style repair
│   ├── utils/
│   │   └── paths.py        # Path management utilities
│   └── cli.py              # Typer-based Command Line Interface
├── styles/suse-styles/     # Official SUSE Vale rulesets and dictionaries
├── data/
│   ├── inputs/             # Source .md files
│   └── outputs/            # Transpiled .adoc files
└── tests/                  # Pytest suite for structural integrity
```

## ✨ Features Implemented (Phase 1)

### 1. Advanced Component Mapping

| Markdown | AsciiDoc (Antora) | Implementation Detail |
| --- | --- | --- |
| `:::info` / `:::tip` | `[IMPORTANT]` / `[TIP]` | Converts to full block delimiters (`====`) |
| `> **Note**:` | `[NOTE]` | Promotes blockquotes to formal Admonition blocks |
| `<details><summary>` | `[%collapsible]` | Preserves summary text as the block title |
| `[Title](./file.md)` | `xref:file.adoc[Title]` | Normalizes paths and strips leading `./` |
| `***bold-italic***` | `*_bold-italic_*` | Fixes complex nested formatting |

### 2. Structural Fixes

* **Header Protection**: Prevents syntax collisions by converting headers inside Admonitions into bold text.
* **List Normalization**: Fixes nesting depth in mixed lists (for example, numbered items inside bullets).
* **Path Sanitization**: Automatically strips redundant `./` from cross-references for Antora compliance.
* **Whitespace Management**: Collapses triple-newlines and ensures tight attribute-to-block alignment.

## 🛠 Installation & Usage

### Prerequisites

* [Python 3.13+](https://www.python.org/)
* [uv](https://github.com/astral-sh/uv) (Package manager)
* [kramdoc](https://github.com/asciidoctor/kramdown-asciidoc) (`gem install kramdown-asciidoc`)
* [Vale](https://vale.sh/) (Style linter)

### Setup

```bash
# Install dependencies
uv sync
```

### Running the Transpiler

To convert a single file and run the SUSE style linter:

```bash
uv run transpile run --file <filepath>
# Example
uv run transpile run --file data/inputs/test.md
```

Output will be saved as `data/outputs/` with a terminal report of any style violations.

## 🔍 Validation Workflow

The tool currently implements a **Convert-then-Lint** strategy:

1. **Conversion**: Generates the `.adoc` file in `data/outputs/`.
2. **Linting**: Automatically triggers **Vale** using the rules in `styles/suse-styles/`.
3. **Reporting**: Prints a color-coded report to the terminal identifying style violations (for example, `wifi` vs `Wi-Fi`, or use of future tense `will`).
