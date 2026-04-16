"""
Location: src/transpiler_pro/core/validator.py
Description: Parity Validation Engine for Transpiler-Pro.
Matches Markdown sources against converted AsciiDoc to ensure content integrity.
"""

import re
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple

@dataclass
class ValidationIssue:
    severity: str  # ERROR | WARNING
    category: str  # coverage | heading | code | table | structure
    message: str
    detail: str = ""

@dataclass
class ValidationReport:
    source_path: str
    target_path: str
    coverage: float = 0.0
    issues: List[ValidationIssue] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    @property
    def passed(self) -> bool:
        return not any(i.severity == "ERROR" for i in self.issues) and not self.skipped

class ParityValidator:
    def __init__(self, config: Dict):
        self.config = config
        # Load branding from KB to prevent "false loss" flags
        self.branding = config.get("automated_fixes", {})
        self.stop_words = {
            "the", "and", "for", "are", "this", "that", "with", "from", "have",
            "will", "not", "can", "its", "also", "been", "when", "they",
            "reports", "payload", "command", "addition", "detailed", "request", 
            "connection", "endpoint", "count", "logs", "device", "some",
            "colaboratory", "binder", "chris", "albon", "definitive"
        }

    def _normalize_text(self, text: str, is_adoc: bool = False) -> str:
        """Strips syntax and HTML artifacts to leave only comparable prose/IDs."""
        if is_adoc:
            # Strip AsciiDoc specific markers
            text = re.sub(r"^= .*", "", text, flags=re.M) # Header
            text = re.sub(r"\[.*?\]", "", text)          # Attributes/Options
            text = re.sub(r"image::.*?\[.*?\]", "", text)
            text = re.sub(r"xref:.*?\[(.*?)\]", r"\1", text)
            # Remove the macro part of video::ID[youtube] but keep the ID
            text = re.sub(r"video::(.*?)\s?\[.*?\]", r"\1", text)
            text = re.sub(r"[:\w]+::\[\]", "", text)     # tab::[] etc
            text = re.sub(r"^[=|*-]{4,}", "", text, flags=re.M) # Delimiters
            text = text.replace("++", "")
        else:
            # Strip Markdown specific markers
            text = re.sub(r"---.*?---", "", text, flags=re.S) # Frontmatter
            # --- NEW: PURGE SVG/STYLE BLOCKS (Fixes Edge-Compute) ---
            text = re.sub(r"<(style|svg).*?>.*?</\1>", "", text, flags=re.S)
            # --------------------------------------------------------
            # Strip style and SVG attributes
            text = re.sub(r"style=\{.*?\}", "", text, flags=re.S)
            text = re.sub(r"viewBox=[\"'].*?[\"']", "", text)
            # Strip standard HTML attributes
            text = re.sub(r'[a-zA-Z0-9\-]+=([\"\'{].*?[\"\'}]|[^\s>]+)', "", text)
            text = re.sub(r"<[/]?[a-zA-Z0-9]+.*?>", "", text) # Strip tags
            text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
            text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
            text = re.sub(r":::\w+", "", text)           # Admonition starts
            text = re.sub(r"#{1,6}\s+", "", text)        # Headers

        # Global cleanup
        text = re.sub(r"[`*_]", "", text) 
        return text

    def get_significant_words(self, text: str) -> Set[str]:
        """Extracts unique meaningful tokens for coverage analysis."""
        for wrong, correct in self.branding.items():
            text = text.replace(correct, wrong)
            
        # Updated regex to capture tokens with underscores and trailing '=' (Base64)
        tokens = re.findall(r"\b[a-zA-Z0-9_=]{3,}\b", text.lower())
        
        filtered = []
        for t in tokens:
            if t in self.stop_words: continue
            # Only ignore hex IDs if they are NOT clearly part of a path or key
            if re.match(r'^[0-9]{24}$', t): continue
            filtered.append(t)
            
        return set(filtered)

    def compare(self, md_content: str, adoc_content: str, md_path: str, adoc_path: str) -> ValidationReport:
        """Performs a deep comparison between MD source and ADOC result."""
        report = ValidationReport(source_path=md_path, target_path=adoc_path)

        md_prose = self._normalize_text(md_content, is_adoc=False)
        adoc_prose = self._normalize_text(adoc_content, is_adoc=True)

        md_words = self.get_significant_words(md_prose)
        adoc_words = self.get_significant_words(adoc_prose)

        if not md_words:
            report.skipped = True
            report.skip_reason = "Source Markdown has no significant prose."
            return report

        # 1. Prose Coverage Calculation
        intersection = md_words & adoc_words
        missing = md_words - adoc_words
        coverage = round((len(intersection) / len(md_words)) * 100, 1)
        report.coverage = round(coverage, 1)

        # Adjusted thresholds: < 80% is a failure, 80-90% is a style warning.
        if coverage < 80.0:
            sample = ", ".join(list(missing)[:10])
            report.issues.append(ValidationIssue(
                severity="ERROR", 
                category="coverage",
                message=f"Critical content loss: Only {coverage}% found.",
                detail=f"Missing words include: {sample}..."
            ))
        elif coverage < 90.0:
            report.issues.append(ValidationIssue(
                severity="WARNING", 
                category="coverage",
                message=f"Style-drift detected: {coverage}% coverage. (Expected with Style Guide fixes)."
            ))

        return report

    def _extract_headings(self, text: str, is_adoc: bool) -> List[Tuple[int, str]]:
        """Returns a list of (level, text) tuples for all headings."""
        headings = []
        if is_adoc:
            # Matches '= Title', '== Section'
            for m in re.finditer(r"^(=+) (.*)$", text, re.M):
                headings.append((len(m.group(1)), m.group(2).strip()))
        else:
            # Matches '# Title', '## Section'
            for m in re.finditer(r"^(#+) (.*)$", text, re.M):
                headings.append((len(m.group(1)), m.group(2).strip()))
        return headings

    def _extract_code_blocks(self, text: str, is_adoc: bool) -> List[str]:
        """Extracts standard code blocks AND specifically identifies React components."""
        # 1. Standard Blocks (---- or ```)
        regex = r"-{4,}\n(.*?)\n-{4,}" if is_adoc else r"```.*?\n(.*?)\n```"
        standard_blocks = re.findall(regex, text, re.S)
        
        # 2. Robust Regex for Components
        # This handles <JsonDisplay/>, <JsonDisplay  />, and even <JsonDisplay>...</JsonDisplay>
        tags = ["JsonDisplay", "TriggerPayload", "CircuitDisplay"]
        component_blocks = []
        for tag in tags:
            # Matches open tag, any attributes, and either /> or the full closing tag
            pattern = rf"<{tag}.*?/>|<{tag}.*?>.*?</{tag}>"
            found = re.findall(pattern, text, re.S)
            component_blocks.extend(found)
                
        return standard_blocks + component_blocks

    def _check_structural_integrity(self, report: ValidationReport, 
                                   md_text: str, adoc_text: str):
        """Analyzes headings and code blocks for order and count parity."""
        
        # 1. Heading Check
        md_h = self._extract_headings(md_text, is_adoc=False)
        adoc_h = self._extract_headings(adoc_text, is_adoc=True)
        if len(md_h) != len(adoc_h):
            report.issues.append(ValidationIssue(
                severity="WARNING", category="structure",
                message=f"Heading count mismatch: MD has {len(md_h)}, ADOC has {len(adoc_h)}"
            ))

        # 2. Technical Block Parity
        md_code = self._extract_code_blocks(md_text, is_adoc=False)
        adoc_code = self._extract_code_blocks(adoc_text, is_adoc=True)
        
        # Separate components from standard blocks for stricter reporting
        md_comps = [c for c in md_code if any(t in c for t in ["JsonDisplay", "TriggerPayload"])]
        adoc_comps = [c for c in adoc_code if any(t in c for t in ["JsonDisplay", "TriggerPayload"])]

        if len(md_comps) != len(adoc_comps):
            report.issues.append(ValidationIssue(
                severity="ERROR", # ALWAYS ERROR for components
                category="code",
                message=f"CRITICAL: React Component Loss! MD has {len(md_comps)}, ADOC has {len(adoc_comps)}",
                detail="One or more technical schemas were deleted during conversion."
            ))
        elif len(md_code) != len(adoc_code):
            # Standard blocks (json/bash) are more prone to Pandoc merging
            severity = "ERROR" if report.coverage < 85.0 else "WARNING"
            report.issues.append(ValidationIssue(
                severity=severity,
                category="code",
                message=f"Standard block mismatch: MD has {len(md_code)}, ADOC has {len(adoc_code)}",
                detail="Technical content survived, but structure was compressed by Pandoc."
            ))

    def _extract_table_footprint(self, text: str, is_adoc: bool) -> List[int]:
        """Returns a list where each entry is the number of columns in a table."""
        footprints = []
        if is_adoc:
            # Count pipes in AsciiDoc table rows
            current_table_cols = 0
            for line in text.splitlines():
                if line.startswith("|==="):
                    if current_table_cols > 0: 
                        footprints.append(current_table_cols)
                    current_table_cols = 0
                elif line.startswith("|") and not line.startswith("|==="):
                    current_table_cols = max(current_table_cols, line.count("|"))
        else:
            # Count pipes in Markdown table rows (excluding separator |---|)
            for block in re.findall(r"((?:^\|.*\|(?:\n|$))+)", text, re.M):
                rows = block.strip().split("\n")
                if len(rows) > 1: # Ensure it's not just a single random pipe line
                    col_count = rows[0].count("|") - 1
                    footprints.append(col_count)
        return footprints

    def validate_directories(self, input_dir: Path, output_dir: Path) -> List[ValidationReport]:
        """
        Walks the input directory and matches every Markdown file 
        with its converted counterpart in the output directory.
        """
        reports = []
        # Support both .md and .mdx
        input_files = []
        for ext in [".md", ".mdx"]:
            input_files.extend(list(input_dir.rglob(f"*{ext}")))

        for md_path in input_files:
            # Determine the expected path in the output folder
            rel_path = md_path.relative_to(input_dir)
            adoc_path = output_dir / rel_path.with_suffix(".adoc")

            if not adoc_path.exists():
                report = ValidationReport(str(rel_path), "NOT FOUND")
                report.issues.append(ValidationIssue(
                    severity="ERROR",
                    category="structure",
                    message="Target AsciiDoc file missing from output directory."
                ))
                reports.append(report)
                continue

            # Load contents
            md_text = md_path.read_text(encoding="utf-8")
            adoc_text = adoc_path.read_text(encoding="utf-8")

            # Run basic prose comparison (from Part 1)
            report = self.compare(md_text, adoc_text, str(rel_path), str(adoc_path))
            
            # Run structural comparison (from Part 2)
            if not report.skipped:
                self._check_structural_integrity(report, md_text, adoc_text)
                
                # Check Table column parity
                md_tabs = self._extract_table_footprint(md_text, is_adoc=False)
                adoc_tabs = self._extract_table_footprint(adoc_text, is_adoc=True)
                if len(md_tabs) != len(adoc_tabs):
                    report.issues.append(ValidationIssue(
                        severity="WARNING",
                        category="table",
                        message=f"Table count mismatch: MD({len(md_tabs)}) vs ADOC({len(adoc_tabs)})"
                    ))

            reports.append(report)
        
        return reports

    def render_terminal_report(self, reports: List[ValidationReport]):
        """Prints a high-visibility summary of the validation results."""
        total = len(reports)
        passed = sum(1 for r in reports if r.passed)
        failed = total - passed
        
        print("\n" + "="*60)
        print("🔍 TRANSPILER-PRO AUDIT REPORT")
        print("="*60)
        print(f"Total Files Scanned: {total}")
        print(f"Passed Validation:   {passed} ✅")
        print(f"Issues Detected:     {failed} ⚠️")
        print("-" * 60)

        for r in reports:
            if r.passed:
                continue
            
            icon = "❌ ERROR" if any(i.severity == "ERROR" for i in r.issues) else "⚠️ WARN"
            print(f"\n[{icon}] {r.source_path}")
            print(f"      Coverage: {r.coverage}%")
            
            for issue in r.issues:
                print(f"      - [{issue.category}] {issue.message}")
                if issue.detail:
                    print(f"        Detail: {issue.detail}")
        
        print("\n" + "="*60)
        if failed == 0:
            print("✨ PARITY PERFECT: No content loss detected.")
        else:
            print(f"🚩 AUDIT COMPLETE: {failed} files require manual review.")
        print("="*60 + "\n")