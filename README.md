# 🚀 Transpiler-Pro

**Transpiler-Pro** is an enterprise-grade documentation pipeline designed to transform **Markdown** into **Antora-compliant AsciiDoc**. Tailored specifically for SUSE technical standards, it goes beyond simple conversion by utilizing Natural Language Processing (NLP) to "heal" linguistic errors, shift tenses, and enforce branding.

## 📌 Core Mission

Transitioning legacy Markdown to AsciiDoc often results in "broken" UI components (tabs, collapsibles) and inconsistent grammar. Transpiler-Pro automates the tedious parts of this migration:

1. **Structural Integrity**: Converts complex Markdown (Admonitions, Collapsibles, Tables) without breaking syntax.
2. **Style Validation**: Checks content against the official **SUSE Vale Style Guide**.
3. **Linguistic Healing**: Uses AI to automatically fix future tense ("will") and wordiness.
4. **Branding Enforcement**: Dynamically ensures `wifi` becomes `Wi-Fi` and `suse` becomes `SUSE`.

## ⚙️ The "Shield-Convert-Repair" Architecture

Transpiler-Pro operates using a multi-stage "Transformation and Healing" process:

### Phase X: Structural Conversion (The Converter)

Standard converters often mangle Docusaurus-style admonitions (`:::note`) or HTML `<details>`. 

* **Shielding Engine**: Uses regex to identify these complex blocks and replace them with unique temporary tokens (Shields).
* **Pandoc Integration**: The "clean" file is converted to AsciiDoc.
* **Restoration Pass**: Replaces tokens with high-fidelity, Antora-compliant AsciiDoc syntax (e.g., `[%collapsible]`).

### Phase Y: Linguistic Repair (The NLP Engine)

Unlike simple find-and-replace tools, Transpiler-Pro understands **context** using the **spaCy `en_core_web_sm`** model.

* **Dependency Parsing**: It identifies the relationship between a subject and a verb (e.g., "The user will execute").
* **Morphological Conjugation**: It doesn't just delete "will"; it conjugates the head verb to the correct present tense form ("executes"), ensuring subject-verb agreement.
* **Surgical Edits**: Edits are applied using character offsets rather than global regex to prevent "collision bugs" (where fixing one word accidentally breaks another).

## 📂 Project Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Structural transformation & block restoration (Phase X)
│   │   ├── linter.py       # Style sensing via Vale CLI
│   │   ├── repair.py       # NLP-driven Tense & Subject-Verb Agreement (Phase Y)
│   │   └── fixer.py        # Rule-based repair (Spelling & Branding)
│   ├── cli.py              # Typer orchestration (The Entry Point)
├── styles/suse-styles/     # Official SUSE Vale rulesets (Synced via Git)
├── data/
│   ├── inputs/             # Place your .md files here
│   ├── intermediate/       # Raw .adoc conversions (Pre-repair)
│   ├── outputs/            # Final "healed" .adoc files
│   └── knowledge_base.json # Branding & Technical Term dictionary
└── pyproject.toml          # Central configuration for the entire pipeline
```

## 🛠 Installation & Setup (Reviewer Guide)

Follow these steps to set up the environment locally. Transpiler-Pro uses `uv` for lightning-fast, reproducible builds.

### 1. Prerequisites

Ensure you have the following installed on your system:

* **Python 3.12+**
* **uv** (Recommended: `brew install uv` or `pip install uv`)
* **Pandoc** (`brew install pandoc` or `zypper install pandoc`)
* **Vale CLI** (`brew install vale` or `zypper install vale`)

### 2. Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/transpiler-pro.git
cd transpiler-pro

# Install Python dependencies and create virtual environment
uv sync

# Download the NLP Linguistic Model (Required for Phase Y)
uv run python -m spacy download en_core_web_sm
```

### 3. Initialize Styles

Sync the official openSUSE style guide to your local machine:
```bash
uv run transpiler-pro sync
```

## 🚀 Usage Guide

### Full Pipeline (Recommended)

This command runs the entire sequence: Sync ➜ Convert ➜ Repair.

```bash
# Process everything in data/inputs/
uv run transpiler-pro full-run

# Process a specific file only
uv run transpiler-pro full-run --file my-guide.md
```

### Granular Control

If you want to run phases individually for debugging:

```bash
# Step 1: Convert only (MD ➜ ADOC)
# For all files:
uv run transpiler-pro x-convert
# For a specific file:
uv run transpiler-pro x-convert --file guide.md

# Step 2: Repair only (Linguistic Healing)
# For a single file:
uv run transpiler-pro y-repair
# For a specific file:
uv run transpiler-pro y-repair --file guide.adoc
```

## 📊 Audit & Quality Control

Transpiler-Pro doesn't just fix text; it provides a **Validation Report**.

1. **Automated Fixes**: The CLI will report exactly how many items were "Auto-Healed."
2. **Audit Logs**: Any complex issues that require a human eye are logged in the terminal with line numbers.
3. **Style Guide Perfect**: If the tool says "Document is style-guide perfect," it means it passed a final validation pass against the official SUSE rules.

## 🧪 Development & Testing

To verify the NLP logic and structural regex:

```bash
# Run the test suite
uv run pytest

# Generate the API Reference (Project Portal)
uv run python docs.py
```
