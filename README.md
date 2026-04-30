# 🚀 Transpiler-Pro

**Transpiler-Pro** is an enterprise-grade documentation pipeline designed to transform **Markdown** into AsciiDoc. Tailored specifically for SUSE technical standards, it goes beyond simple conversion by utilizing Natural Language Processing (NLP) to "heal" linguistic errors, shift tenses, enforce branding, and prepare the output for multiple publishing formats (HTML, XML, and PDF).

## 📌 Core Mission

Transitioning legacy Markdown to AsciiDoc often results in "broken" UI components (tabs, collapsibles), dead links, and inconsistent grammar. Transpiler-Pro automates the tedious parts of this migration through five key pillars:

1. **Structural Integrity & SEO Stability** - Converts complex Markdown into Antora-compliant AsciiDoc while "freezing" headers with hardcoded, SEO-friendly anchors to prevent broken links.
2. **Dynamic White-Labeling** - Automatically maps hardcoded product names to centralized Antora `{attributes}`, ensuring single-source-of-truth branding.
3. **Style Validation** - Checks content against the official SUSE Vale Style Guide.
4. **Linguistic Healing** - Uses AI to automatically fix future tense and wordiness while maintaining subject-verb agreement.
5. **Content Parity Audit** - Automatically validates that no text, code blocks, or headings were lost during the conversion process via a high-fidelity parity engine.

## ⚙️ The "Shield-Convert-Repair-Audit" Architecture

Transpiler-Pro operates using a multi-stage "Transformation and Healing" process:

### Phase X - Structural Conversion (The Converter)

Standard converters often mangle Docusaurus-style components or generate unstable IDs.

* **Shielding Engine** - Uses a "Shield-Body-End" tokenization strategy to protect complex blocks (like `:::note` or `<JsonDisplay>`) from being mangled.
* **The "Slug & Freeze" ID Engine** - Automatically injects unique, persistent anchors (e.g., `[#access-keys]`) into every heading. It is fully DocBook-aware, dynamically switching to `[id="..."]` syntax if a title contains dots, ensuring valid enterprise XML builds.
* **Antora Cross-Reference Router** - Safely translates relative Markdown links into strict Antora xref:file.adoc#anchor[Text] macros.
* **PDF-Ready Image Scaling** - Automatically scans all images and dynamically injects `pdfwidth=100%,scalewidth=100%` parameters, ensuring screenshots scale perfectly when building PDFs via DAPS or Antora.
* **Attribute & Asset Orchestration** - Detects non-Markdown files (`.yml`, images) for exact project mirroring. Furthermore, it dynamically auto-generates the master `attributes.adoc` file containing all SUSE product variables.

### Phase Y - Linguistic Repair (The NLP Engine)

Unlike simple find-and-replace tools, Transpiler-Pro understands **context** using the **spaCy `en_core_web_sm`** model.

* **Dependency Parsing** - It identifies the relationship between a subject and a verb (for example, "The user will execute").
* **Morphological Conjugation** - It conjugates the head verb to the correct present tense form ("executes"), ensuring subject-verb agreement rather than just deleting words.
* **Surgical Edits** - Edits are applied using character offsets to prevent "collision bugs" where fixing one word accidentally breaks another.

### Phase Z - Content Parity Audit (The Validator)

To guarantee zero data loss, the pipeline concludes with a high-velocity validation engine optimized for technical documentation:

* **Component-Aware Scanning** - Unlike standard diff tools, the validator "sees" inside React/JSX components (like `<JsonDisplay>`), ensuring complex JSON schemas and technical specs are preserved 1:1.
* **Technical Token Normalization** - A specialized tokenizer filters out formatting "noise" (hex fragments, date fluctuations, and punctuation) to focus the audit on actual prose and critical API parameters.
* **High-Velocity Set Logic** - Optimized using Set Theory and lazy-loading structural diffs, reducing audit times for large libraries from **20 minutes to under 15 seconds**.

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
│   ├── audit-logs/         # Detailed parity reports (Phase Z evidence)
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

**Transpiler-Pro** is designed for high portability. While it defaults to the internal `data/` directory structure, every command supports custom path flags, allowing you to target any external documentation repository.

### 1. Full Pipeline (The "Golden" Path)

The `full-run` command orchestrates the entire sequence (**Sync ➜ Convert ➜ Repair ➜ Audit**). This is the recommended way to ensure your content is structurally stable, linguistically "healed," and verified for zero content loss. It also generates an auto-generated `attributes.adoc` file in the base directory of the generated output.

```bash
# Option A: Bypass the audit for large-scale rapid prototyping
uv run transpiler-pro full-run --no-audit

# Option B: Standard run using default data/ folders
uv run transpiler-pro full-run

# Option C: Target external directories (Enterprise Portability)
uv run transpiler-pro full-run --input ~/my-project/docs --output ~/my-project/dist
```

### 2. Individual Phase Control

For granular debugging or specialized workflows, you can trigger individual phases of the transformation engine.

#### Phase X: Structural Conversion

Converts Markdown to AsciiDoc, injects SEO-friendly persistent IDs, and mirrors assets (images, `.yml`) to the output path.

```bash
# If you want to use the default data/ folders, simply run:
uv run transpiler-pro x-convert

# Convert Markdown to AsciiDoc by providing input and output directories
uv run transpiler-pro x-convert --input ./raw-md --output ./intermediate-adoc
```

#### Phase Y: Linguistic Healing

Processes AsciiDoc files through the NLP engine to fix future tense, apply branding rules, and resolve subject-verb agreement.

```bash
# If you want to use the default data/ folders, simply run:
uv run transpiler-pro y-repair

# Run the repair phase with custom paths
uv run transpiler-pro y-repair --input ./intermediate-adoc --output ./final-adoc
```

#### Phase S: Style Synchronization

Force-updates the local SUSE Vale style guides from the remote repository.

```bash
uv run transpiler-pro sync
```

### 📊 Verification & Build Integrity

Transpiler-Pro includes two distinct layers of quality control to ensure "Technical Parity" and "Syntax Perfection."

#### 1. Content Parity Audit (Phase Z)

This verifies that no technical information was lost. It performs a high-fidelity token comparison between the source Markdown and the generated AsciiDoc, filtering out formatting noise.

```bash
# If you want to use the default data/ folders, simply run:
uv run transpiler-pro audit

# Verify integrity between any two directories
uv run transpiler-pro audit --input ./source-md --output ./converted-adoc
```

#### 2. Asciidoctor Build Check (The "Check" Command)

The ultimate syntax test. It renders your `.adoc` files into a mirrored HTML preview folder using the official `asciidoctor` parser. It is configured to fail on `WARN` to catch duplicate IDs or broken macros.

```bash
# Generate a complete HTML preview in data/build-preview/html directory
uv run transpiler-pro check

# Generate the xml in data/build-preview/xml directory
uv run transpiler-pro check --docbook

# Generate a complete HTML preview in a sandbox directory
uv run transpiler-pro check --input ./final-adoc --build-dir ./preview-html

# Target a specific file for rapid syntax debugging
uv run transpiler-pro check --file instance.adoc --input ./data/outputs
```

### Targeted Processing

If you are working on a specific document and do not want to process the entire library, use the `--file` (or `-f`) flag. This works across `full-run`, `x-convert`, `y-repair`, and `check`.

```bash
# Run the entire pipeline for a single file
uv run transpiler-pro full-run --file security-guide.md

# Build a preview for just one file
uv run transpiler-pro check --file security-guide.adoc
```

## 📊 Audit & Quality Control

Transpiler-Pro provides a two-layered validation system to ensure your documentation is both linguistically polished and structurally complete.

### 1. Linguistic Healing Logs (Phase Y)

During the repair phase, the tool tracks automated improvements and identifies manual tasks:

* **Automated Fixes** - The CLI reports exactly how many grammar, tense, and branding issues were auto-healed.
* **Review Logs** - Any complex stylistic issues that require a human eye are logged in the terminal with line numbers and rule IDs.
* **Style-Guide Perfect** - A confirmation that the document has passed 100% of the SUSE official rules.

### 2. Content Parity Dashboard (Phase Z)

After conversion, the tool runs a strict comparison between the Markdown source and the AsciiDoc result:

* **Prose Coverage** - A percentage-based check ensuring the core message was preserved.
* **Snippet Defense** - A zero-tolerance check for code blocks; if a technical snippet is lost, the audit flags a **CRITICAL ERROR**.
* **Detailed Audit Logs** - Generates exhaustive JSON evidence in `data/audit-logs/` for any file falling below the 98% threshold, allowing for rapid debugging of technical edge cases.

## 🧪 Development & Testing

To verify the NLP logic, structural regex, and parity engine:

```bash
# Run the test suite (Unit tests for Shields and NLP)
uv run pytest

# Generate the API Reference (Project Portal)
uv run python docs.py
```
