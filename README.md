# 🚀 Transpiler-Pro

**Transpiler-Pro** is an enterprise-grade documentation pipeline designed to transform **Markdown** into **Antora-compliant AsciiDoc**. Tailored specifically for SUSE technical standards, it goes beyond simple conversion by utilizing Natural Language Processing (NLP) to "heal" linguistic errors, shift tenses, and enforce branding.

## 📌 Core Mission

Transitioning legacy Markdown to AsciiDoc often results in "broken" UI components (tabs, collapsibles) and inconsistent grammar. Transpiler-Pro automates the tedious parts of this migration through four key pillars:

1. **Structural Integrity** - Converts complex Markdown (Admonitions, Collapsibles, Tables) and mirrors assets (images, `.yml`) without breaking syntax.
2. **Style Validation** - Checks content against the official **SUSE Vale Style Guide**.
3. **Linguistic Healing** - Uses AI to automatically fix future tense and wordiness while maintaining subject-verb agreement.
4. **Content Parity Audit** - **(New)** Automatically validates that no text, code blocks, or headings were lost during the conversion process via a high-fidelity parity engine.

## ⚙️ The "Shield-Convert-Repair-Audit" Architecture

Transpiler-Pro operates using a multi-stage "Transformation and Healing" process:

### Phase X - Structural Conversion (The Converter)

Standard converters often mangle Docusaurus-style admonitions (`:::note`) or HTML `<details>`. 

* **Shielding Engine** - Uses regex to identify these complex blocks and replace them with unique temporary tokens (Shields).
* **Asset Mirroring** - Automatically detects and copies non-Markdown files (for example, `_category_.yml`, images) to the output directory to maintain project structure.
* **Restoration Pass** - Replaces tokens with high-fidelity, Antora-compliant AsciiDoc syntax (for example, `[%collapsible]`).

### Phase Y - Linguistic Repair (The NLP Engine)

Unlike simple find-and-replace tools, Transpiler-Pro understands **context** using the **spaCy `en_core_web_sm`** model.

* **Dependency Parsing** - It identifies the relationship between a subject and a verb (for example, "The user will execute").
* **Morphological Conjugation** - It conjugates the head verb to the correct present tense form ("executes"), ensuring subject-verb agreement rather than just deleting words.
* **Surgical Edits** - Edits are applied using character offsets to prevent "collision bugs" where fixing one word accidentally breaks another.

### Phase Z - Content Parity Audit (The Validator)

To guarantee zero content loss during the complex transformation, the pipeline concludes with a high-fidelity audit:

* **Semantic Word Coverage** - Compares significant tokens between Markdown and AsciiDoc, accounting for branding fixes so that "wifi" → "Wi-Fi" is marked as a 100% match.
* **Structural Parity** - Validates that the number of headings and tables matches the source exactly.
* **Snippet Protection** - Performs a strict count and similarity check on all code blocks to ensure technical instructions remain intact.

## 📂 Project Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Structural transformation & block restoration (Phase X)
│   │   ├── linter.py       # Style sensing via Vale CLI
│   │   ├── repair.py       # NLP-driven Tense & Subject-Verb Agreement (Phase Y)
│   │   ├── validator.py    # Content Parity & Audit logic (Phase Z)
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

## 🛠 Installation & Setup

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

# Download the NLP Linguistic Model (Required for Phase Y & Z)
uv run python -m spacy download en_core_web_sm
```

### 3. Initialize Styles

Sync the official openSUSE style guide to your local machine:

```bash
uv run transpiler-pro sync
```

## 🚀 Usage Guide

Transpiler-Pro is highly flexible. While it defaults to the internal `data/` directory, you can point it at any external documentation repository using path flags.

### 1. Full Pipeline (Recommended)

The `full-run` command executes the entire sequence (**Sync ➜ Convert ➜ Repair ➜ Audit**). This is the safest way to ensure your content is both linguistically "healed" and structurally identical to the source.

```bash
# Option A: Use internal data/ folders (Default)
uv run transpiler-pro full-run

# Option B: Target external directories (Portable Mode)
uv run transpiler-pro full-run --input ~/projects/my-docs/src --output ~/projects/my-docs/dist
```

> **Note**: By default, `full-run` triggers an automatic audit at the end. You can skip this by adding the `--no-audit` flag.

### 2. Individual Phase Control

You can specify custom paths for individual phases for granular debugging or specific workflows:

```bash
# Phase X: Structural Mirroring & Conversion
# Converts .md and mirrors assets (images/yml) to the output path
uv run transpiler-pro x-convert --input ./raw-md --output ./raw-adoc

# Phase Y: Linguistic Healing
# Processes .adoc files for grammar and branding
uv run transpiler-pro y-repair --input ./raw-adoc --output ./final-docs

# Phase Z: Content Parity Audit (Manual)
# Manually verify integrity between any two MD and ADOC directories
uv run transpiler-pro audit --input ./source-md --output ./converted-adoc
```

### 3. Target Specific Files

If you only need to process a single document within a directory:

```bash
uv run transpiler-pro full-run --file security-guide.md
```

## 📊 Audit & Quality Control

Transpiler-Pro provides a two-layered validation system to ensure your documentation is both linguistically polished and structurally complete.

### 1. Linguistic Healing Logs (Phase Y)

During the repair phase, the tool tracks automated improvements and identifies manual tasks:

* **Automated Fixes**: The CLI reports exactly how many grammar, tense, and branding issues were auto-healed.
* **Review Logs**: Any complex stylistic issues that require a human eye are logged in the terminal with line numbers and rule IDs.
* **Style-Guide Perfect**: A confirmation that the document has passed 100% of the SUSE official rules.

### 2. Content Parity Dashboard (Phase Z)

After conversion, the tool runs a strict comparison between the Markdown source and the AsciiDoc result:

* **Prose Coverage**: A percentage-based check ensuring the core message was preserved.
* **Structural Consistency**: Confirms that the number of headings and tables remains identical.
* **Snippet Defense**: A zero-tolerance check for code blocks; if a technical snippet is lost, the audit flags it as a **CRITICAL ERROR**.

## 🧪 Development & Testing

To verify the NLP logic, structural regex, and parity engine:

```bash
# Run the test suite (Unit tests for Shields and NLP)
uv run pytest

# Run a manual audit on existing directories
uv run transpiler-pro audit --input ./source --output ./dist

# Generate the API Reference (Project Portal)
uv run python docs.py
```
