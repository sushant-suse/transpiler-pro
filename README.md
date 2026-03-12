# 🚀 Transpiler-Pro

**Transpiler-Pro** is an enterprise-grade documentation pipeline designed to transform **Markdown** into **Antora-compliant AsciiDoc**. Tailored specifically for SUSE technical standards, it goes beyond simple conversion by utilizing Natural Language Processing (NLP) to "heal" linguistic errors and enforce branding.

## 📌 What it Does

The tool automates the tedious parts of documentation migration:

1. **Converts** complex Markdown structures (Admonitions, Collapsibles, Tables) to AsciiDoc.
2. **Validates** content against the official **SUSE Vale Style Guide**.
3. **Auto-Heals** linguistic issues like future tense ("will") and wordiness.
4. **Enforces Branding** dynamically (for example, ensuring `wifi` always becomes `Wi-Fi`).

## ⚙️ How it Works (The Pipeline)

Transpiler-Pro operates in three distinct phases utilizing specialized engines:

- **Phase X (Structural)**: Uses `kramdoc` combined with a custom **Shielding Engine**. It "shields" Markdown components that standard converters usually break (like `:::note` or `<details>`) and restores them as native AsciiDoc blocks.
- **Phase Y (Linguistic)**: Integrates **spaCy NLP** and **Vale**. It performs dependency parsing to identify modal verbs and applies morphological conjugation to shift sentences into the active present tense.
- **Knowledge Base (The Brain)**: A dynamic `knowledge_base.json` acts as the source of truth for branding, ignored rules, and automated fixes.

## 📂 Project Architecture

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Structural transformation & block restoration
│   │   ├── linter.py       # Style sensing via Vale CLI
│   │   ├── repair.py       # NLP-driven Tense & Branding Engine
│   │   └── fixer.py        # Rule-based Regex repair
│   ├── utils/              # Path & Logger utilities
│   └── cli.py              # Typer orchestration (The Entry Point)
├── styles/suse-styles/     # Official SUSE Vale rulesets (Synced via Git)
├── data/
│   ├── inputs/             # Source .md files
│   ├── intermediate/       # Raw .adoc conversions (Pre-repair)
│   ├── outputs/            # Final "healed" .adoc files
│   ├── logs/               # Clickable Markdown Audit Reports
│   └── knowledge_base.json # Branding & Fix dictionary
└── pyproject.toml          # Pipeline & Tool configuration
```

## 🛠 Installation & Setup

### Prerequisites

- **Python 3.12+**
- **uv** (Fast Python package manager)
- **kramdoc** (`gem install kramdown-asciidoc`)
- **Vale** (`brew install vale` or `zypper install vale`)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/sushant-suse/transpiler-pro.git
cd transpiler-pro

# 2. Install dependencies
uv sync

# 3. Download the NLP Grammar Model
uv run python -m spacy download en_core_web_sm

# 4. Sync the official SUSE Style Guide
uv run transpiler-pro sync
```

## 🚀 Usage & Commands

Transpiler-Pro provides modular commands for every stage of the pipeline.

### 1. Synchronize Styles

Always keep your rules up to date with the official openSUSE style guide.

```bash
uv run transpiler-pro sync
```

### 2. X-Phase: Convert (Markdown ➜ AsciiDoc)

```bash
# Process entire directory
uv run transpiler-pro x-convert

# Process specific file
uv run transpiler-pro x-convert --file sample.md
```

### 3. Y-Phase: Repair (Validate ➜ Heal ➜ Log)

Runs the linter, applies NLP healing, and generates a clickable audit report.

```bash
# Process entire intermediate directory
uv run transpiler-pro y-repair

# Process specific file
uv run transpiler-pro y-repair --file sample.adoc
```

### 4. Full Pipeline (The Combo)

The most efficient way to run: Syncs, Converts and Repairs in one sequence.

```bash
# Run on all files
uv run transpiler-pro full-run

# Run on a specific file
uv run transpiler-pro full-run --file sample.md
```

## 🛡️ Audit Reporting

Every time a repair is run, the tool generates a **Clickable Audit Report** in `data/logs/`.

- **Clickable Links**: Open the exact file and line number in VS Code using the `file://` protocol.
- **Dynamic Actions**: Tells you exactly what to do for remaining issues.
- **Style References**: Direct links to the official SUSE Style Guide documentation.

## 🧪 Testing & Docs

```bash
# Run logic verification tests
uv run pytest

# Generate local documentation
uv run python -m pdoc src/transpiler_pro -o docs
```

## 👨🏻‍💻 Working of Tool

To answer that question with technical precision: Yes, the system uses a **local Natural Language Processing (NLP) model** via the **spaCy** library, specifically the `en_core_web_sm` pipeline. Unlike tools that rely on cloud APIs, Transpiler-Pro performs its linguistic analysis entirely on your machine.

### How the Pipeline Works: From Input to Healed Output

The workflow is a multi-stage "Transformation and Healing" process that can be broken down into four distinct technical steps:

#### 1. Structural Ingestion & Shielding (The Converter)

When you provide a Markdown file, the code does not just "rename" it. First, a **Shielding Engine** uses regular expressions to identify complex components that standard converters often break specifically Docusaurus-style admonitions (`:::note`) and HTML collapsible blocks (`<details>`). It replaces these with temporary unique markers (shields). The "clean" file is then processed by `kramdoc` to handle standard Markdown-to-AsciiDoc conversion. Finally, a **Restoration Pass** replaces those shields with high-fidelity, Antora-compliant AsciiDoc syntax (like `[%collapsible]`).

#### 2. Diagnostic Linting (The Style Sensor)

The raw AsciiDoc is then fed into the **Linter Layer**, which invokes the **Vale CLI** locally. This stage compares your text against the **official openSUSE Style Guide** (synced via Git). Instead of just showing errors, the code captures the "Correction Metadata"—the exact line number, the specific rule violated (for example, `common.Will`), and the suggested fix. This metadata acts as the "map" for the next phase.

#### 3. Local NLP Healing (The Repair Engine)

This is where the local **spaCy model** comes in. The code loads the `en_core_web_sm` model to perform **Dependency Parsing**. It does not just look for words; it understands the relationship between them.

- **Tense Shifting**: It identifies "Auxiliary + Head" pairs (for example, "will" + "verify"). It then uses a morphological helper to dynamically conjugate the head verb into the third-person singular present ("verifies").
- **Recursive Modal Collapsing**: It handles modal verbs like "should," "must," and "will" even when they modify adjectives or are in passive voice constructions, collapsing them into active present tense.
- **Branding Enforcement**: Simultaneously, an aggressive **Lookaround Regex** pass uses your `knowledge_base.json` to force correct branding (like `Wi-Fi`) by ensuring the terms are not touching other alphanumeric characters, preventing partial-word replacements.

#### 4. Final Audit & Output Generation

Once the text is "healed," the tool performs a **Final Audit Pass**. It runs the linter one last time to see what survived the automated repair. It calculates a "Success Metric" (for example, "57 fixed") and generates a **Clickable Markdown Audit Report**. This report uses the `file://` protocol so that manual reviewers can click a link in the log to open their IDE directly at the exact line of a residual error. The final, production-ready file is then saved to the `outputs/` directory.
