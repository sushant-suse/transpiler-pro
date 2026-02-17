# 🚀 Personal Transpiler-Pro

A high-fidelity documentation transpiler designed to convert **Markdown** into **Antora-compliant AsciiDoc**, specifically tailored for SUSE technical documentation standards.

## 📌 Project Overview

This project goes beyond standard conversion by using a **Smart Three-Phase Pipeline**. It combines deterministic regex-based transformation with **Natural Language Processing (NLP)** to identify and automatically repair style violations.

1. **Phase 1 - Conversion** - Shields complex Markdown components and utilizes `kramdoc` for structural transpilation.
2. **Phase 2 - Validation** - Integrates the **Vale CLI** with official SUSE styles to detect linguistic errors.
3. **Phase 3 - Auto-Heal** - Uses **spaCy NLP** to contextually repair grammar (for example, tense agreement) and surgically fix spelling without hardcoded dictionaries.

Refer to the [System Architecture document]() for an in-depth breakdown of the module interactions and data flow.

## 📂 Folder Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Phase 1: Markdown to AsciiDoc transformation
│   │   ├── linter.py       # Phase 2: Style sensing via Vale
│   │   ├── fixer.py        # Phase 2.5: NLP-driven linguistic repair
│   │   └── refiner.py      # Phase 3: JS-to-Antora Navigation generation
│   ├── utils/
│   │   └── paths.py        # Project-wide path management
│   └── cli.py              # Typer-based orchestration layer
├── styles/                 # Official SUSE Vale rulesets and dictionaries
├── data/
│   ├── inputs/             # Source .md files
│   └── outputs/            # Transpiled and "healed" .adoc files
└── tests/                  # Pytest suite (100% logic coverage)

```

## ✨ Features Implemented

### 1. NLP-Driven Grammar Repair

Unlike basic find-and-replace tools, Transpiler-Pro uses **Dependency Parsing** to ensure grammatical correctness:

- **Contextual Tense Fix**: Replaces "will" (forbidden in SUSE docs). It intelligently chooses "is" or "are" based on whether the subject is singular (e.g., *The system is*) or plural (for example, *We are*).

### 2. Zero-Hardcoded Spelling Fixes

The tool is "Suggestion-Aware." It extracts the recommended correction directly from Vale's rule parameters. If you add a new spelling rule to the SUSE styles, the fixer automatically knows how to repair it without any Python code changes.

### 3. Advanced Component Mapping

| Markdown | AsciiDoc (Antora) | Implementation Detail |
| --- | --- | --- |
| `:::info` / `:::tip` | `[IMPORTANT]` / `[TIP]` | Converts to full block delimiters (`====`) |
| `<details><summary>` | `[%collapsible]` | Preserves summary text as the block title |
| `[Title](./file.md)` | `xref:file.adoc[Title]` | Normalizes paths for Antora compliance |

## 🛠 Installation & Setup

### Prerequisites

- **Python 3.12** (Pinned for spaCy/NumPy binary compatibility)
- **uv** (Modern Python package manager)
- **kramdoc** (`gem install kramdown-asciidoc`)
- **Vale** (`brew install vale`)

### Clone & Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/transpiler-pro.git
cd transpiler-pro

# 2. Create virtual environment and install dependencies
# This will use the pinned Python 3.12 and lock all versions
uv sync

# 3. Download the NLP Grammar Model
# Note: This is required for the 'Auto-Heal' engine to function
uv run python -m spacy download en_core_web_sm
```

## 🚀 Usage

### Running the Full Pipeline

To convert a file, validate it, and **automatically apply repairs**:

```bash
uv run transpile run --file data/inputs/test.md --fix
```

### Running Tests

Ensure the NLP and conversion logic are functioning correctly in your local environment:

```bash
uv run pytest
```
