# 🚀 Personal Transpiler-Pro

[![Build Status](https://img.shields.io/badge/tests-19%20passed-brightgreen)](https://github.com/sushant-suse/transpiler-pro)
[![Coverage](https://img.shields.io/badge/coverage-78%25-blueviolet)](https://github.com/sushant-suse/transpiler-pro)
[![Documentation](https://img.shields.io/badge/docs-pdoc-blue)](https://sushant-suse.github.io/transpiler-pro/)

A high-fidelity documentation transpiler designed to convert **Markdown** into **Antora-compliant AsciiDoc**, specifically tailored for SUSE technical documentation standards.

## 📌 Project Overview

Transpiler-Pro is an enterprise-grade utility that goes beyond standard conversion. It uses a **Smart Multi-Phase Pipeline** to transform, validate, and contextually repair technical documentation.

1. **Phase 1 - Transformation** – Shields Markdown components (admonitions/collapsibles) and utilizes `kramdoc` for structural transpilation.
2. **Phase 2 - Validation** – Integrates the **Vale CLI** with a comprehensive suite of official SUSE styles to detect linguistic and technical errors.
3. **Phase 3 - Auto-Heal & Learning** – Uses **spaCy NLP** for grammatical repair and a dynamic **Knowledge Base** to enforce branding and "learn" new terminology on the fly.

## 📂 Folder Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Structural transformation & block restoration
│   │   ├── linter.py       # Style sensing via Vale CLI
│   │   └── fixer.py        # NLP-driven repair & Knowledge Base management
│   ├── utils/              # Project-wide path management
│   └── cli.py              # Typer-based orchestration & Antora refinement
├── styles/suse-styles/     # Official SUSE Vale rulesets (submodule)
├── data/
│   ├── inputs/             # Source .md files
│   ├── outputs/            # Transpiled and "healed" .adoc files
│   └── knowledge_base.json # The "Brain": Persistent branding & learned terms
├── docs/                   # Auto-generated project documentation (pdoc)
├── tests/                  # Pytest suite verifying core logic
└── pyproject.toml          # Central configuration & NLP special verbs
```

## ✨ Key Features

### 1. NLP-Driven Grammar Repair

Unlike basic find-and-replace tools, Transpiler-Pro uses **Dependency Parsing** to ensure grammatical correctness:

* **Intelligent Tense Shift** - Automatically converts future-tense "will" into the progressive present. It identifies subjects to choose between "is" and "are" (for example, *The system is* vs *Users are*).
* **CVC Verb Doubling** - Corrects verb endings dynamically (for example, *run* -> *running*), with data driven overrides in `pyproject.toml` (for example, *setup* -> *setting up*).

### 2. Self-Learning Knowledge Base

The tool features a **Discovery Engine**. If the linter flags a spelling error not present in the Knowledge Base:

* It applies a capitalization fallback.
* It **logs the new word** to `data/knowledge_base.json` for future sessions.
* **Global Enforcement** - It forces branding (like `SUSE`, `Wi-Fi`, `ID`) even if the linter fails to flag the word.

### 3. Structural Block Restoration

High-fidelity mapping of complex Markdown components to AsciiDoc:

* **Admonitions** - Converts `:::info` blocks to full `[IMPORTANT]` AsciiDoc blocks.
* **Collapsibles** - Maps `<details>` to Antora `[%collapsible]` blocks.
* **XREFs** - Normalizes Markdown links into Antora-compliant `xref:file.adoc[]` format.

## 🛠 Installation & Setup

### Prerequisites

* **Python 3.12+**
* **uv** (Python package manager)
* **kramdoc** (`gem install kramdown-asciidoc`)
* **Vale** (`brew install vale`)

### Setup

```bash
# 1. Sync dependencies
uv sync

# 2. Download the NLP Grammar Model
uv run python -m spacy download en_core_web_sm

# 3. Sync Style Submodules
uv run transpiler-pro run --sync
```

## 🚀 Usage

### Transpilation & Repair

```bash
# Convert, Validate, and Auto-Fix a specific file
uv run transpiler-pro run --file sample.md --fix

# Run on all files in the input directory
uv run transpiler-pro run --fix
```

### Documentation & Testing

```bash
# Generate the documentation suite (API Reference + Self-Transpiled Arch)
uv run python docs.py

# Run the full logic test suite
uv run pytest
```

#### To view the generated documentation:

Open `docs/index.html` in your browser.

Or, navigate to the docs directory and serve it with Python's HTTP server:

```bash
cd docs
python -m http.server 8000
```

Then open `http://localhost:8000` in your browser.
