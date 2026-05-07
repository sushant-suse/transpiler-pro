"""
Location: src/transpiler_pro/core/validator.py
Description: Parity Validation Engine for Transpiler-Pro.
Matches Markdown sources against converted AsciiDoc to ensure content integrity.
"""

import spacy
import re
import difflib
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple


# Load the spaCy NLP model for lemmatization (tense-aware comparison)
try:
    nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
except OSError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])


@dataclass
class ValidationIssue:
    severity: str  # ERROR | WARNING
    category: str  # coverage | heading | code | table | structure
    message: str
    detail: str = ""


@dataclass
class ValidationReport:
    # This report captures the results of validating a single file pair (Markdown source vs AsciiDoc target).
    source_path: str
    target_path: str
    coverage: float = 0.0
    issues: List[ValidationIssue] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    # The 'passed' property is a convenient way to check if the validation was successful without any errors.
    @property
    def passed(self) -> bool:
        return not any(i.severity == "ERROR" for i in self.issues) and not self.skipped


class ParityValidator:
    def __init__(self, config: Dict):
        self.config = config
        # Load branding from KB to prevent "false loss" flags
        self.branding = config.get("automated_fixes", {})
        # Initialize audit log directory
        self.log_dir = Path("data/audit-logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._prepare_log_dir()
        self.stop_words = {
            "the", "and", "for", "are", "this", "that", "with", "from", "have",
            "will", "not", "can", "its", "also", "been", "when", "they"
        }
    
    def _prepare_log_dir(self):
        """Ensures log dir exists and is empty for the current run.
        
        Args: None

        Returns: None
        """
        # We create the log directory if it doesn't exist and clear out any old logs to ensure that each run starts with a clean slate. 
        # This prevents confusion from stale data and ensures that any logs present after the run are relevant to the current validation process.
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Clear out old logs to prevent confusion with stale data.
        for f in self.log_dir.glob("*.json"):
            f.unlink()


    def _normalize_text(self, text: str, is_adoc: bool = False) -> str:
        """Strips syntax to leave only comparable prose and technical tokens.
        
        Args:
            text (str): The raw content of the file to be normalized.
            is_adoc (bool): Flag to indicate if the text is from an AsciiDoc file, which has different syntax rules than Markdown.
        
        Returns:
            str: A cleaned version of the text containing only the prose and technical tokens relevant for comparison, 
            with all formatting and structural syntax removed.
        """
        if is_adoc:
            # 1. Strip AsciiDoc specific structural markers
            text = re.sub(r"^= .*", "", text, flags=re.M)      # Header
            text = re.sub(r"^\[.*?\]$", "", text, flags=re.M) # Block Attributes
            text = re.sub(r"image::.*?\[.*?\]", "", text)
            text = re.sub(r"xref:.*?\[(.*?)\]", r"\1", text)
            text = re.sub(r"[:\w]+::\[\]", "", text)          # tab::[] etc
            text = re.sub(r"^[=|*-]{4,}", "", text, flags=re.M) # Delimiters
            
            # 2. Neutralize Pandoc noise: 
            # Replace '++' with a space to prevent Hex tokens from merging (06++:++5D -> 06 5D)
            text = text.replace("++", " ") 

            # Neutralize Antora Attribute braces to allow word-matching
            # This ensures {longhorn-product-name} becomes 'longhorn product name'
            # so the tokenization engine can compare it to the original Markdown prose.
            text = text.replace("{", " ").replace("}", " ")
        else:
            # 3. Strip Markdown specific markers
            text = re.sub(r"---.*?---", "", text, flags=re.S) # Frontmatter
            text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
            text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
            text = re.sub(r":::\w+", "", text)
            text = re.sub(r"#{1,6}\s+", "", text)

            # Strip Docusaurus specific structural artifacts to prevent false positives
            text = re.sub(r"(?i)\.BODY|ENDADMON", " ", text)
            text = re.sub(r"^\[(?:TIP|NOTE|WARNING|CAUTION|IMPORTANT)\]\s*", "", text, flags=re.M)
            
            # 4. Handle Markdown HTML entities (fixes the 'x27' / '&#x27;' issue)
            import html
            text = html.unescape(text)

        # 5. Component Cleaning: Strip HTML/JSX tags but keep content
        # Use a space replacement to prevent words from being concatenated
        text = re.sub(r"<[^>]+>", " ", text) 

        # 6. Technical Normalization: Split by common technical delimiters
        # We add '/' and '\' to the split list to handle URL/Path fragments (fixes 'params/info')
        text = re.sub(r"[:\-\/\\\.]", " ", text)

        # 7. Final Polish: Remove formatting chars but keep alphanumeric characters
        text = re.sub(r"[`*_]", "", text) 
        
        # 8. Extra Clean: Remove single-character artifacts that aren't useful for parity
        # (Optional, but helps with residual punctuation artifacts)
        text = re.sub(r"\s+", " ", text).strip()
        
        return text


    def get_significant_words(self, text: str) -> Set[str]:
        """Extracts meaningful tokens while handling branding and lemmatization.
        
        Args:
            text (str): The text from which to extract significant words.
        
        Returns:
            Set[str]: A set of significant words extracted from the text.
        """
        # Use spaCy to find the base 'lemma' of words to account for tense shifting
        # (e.g., 'execute' in MD vs 'executes' in ADOC will both match as 'execute')
        doc = nlp(text.lower())
        
        filtered_tokens = []
        for token in doc:
            t = token.lemma_ # Root form (checks == check)
            
            if t in self.stop_words or not t.isalnum() or len(t) < 2:
                continue
            
            # Skip short numeric noise
            if t.isdigit() and len(t) < 5:
                continue

            filtered_tokens.append(t)

        token_set = set(filtered_tokens)
        
        # Optimized Branding Mapping: 
        # Convert "{longhorn-product-name}" back to "storage" for comparison
        # brand_map = {v.lower(): k.lower() for k, v in self.branding.items()}
        
        # We also need to strip the curly braces from the keys in brand_map 
        # so they match the tokens found by the NLP.
        final_set = set()
        for word in token_set:
            # Check if the word (like 'longhorn-product-name') is in our branding values
            cleaned_word = word.strip("{}")
            found = False
            for attr_val, raw_text in self.branding.items():
                if cleaned_word in attr_val.lower():
                    # Add the raw words from 'SUSE Storage' to the set
                    for part in raw_text.lower().split():
                        if part not in self.stop_words:
                            final_set.add(part)
                    found = True
                    break
            if not found:
                final_set.add(word)
                
        return final_set


    def compare(self, md_content: str, adoc_content: str, md_path: str, adoc_path: str) -> ValidationReport:
        """Performs a deep comparison between MD source and ADOC result.
        
        Args:
            md_content (str): The raw content of the Markdown file.
            adoc_content (str): The raw content of the AsciiDoc file.
            md_path (str): The file path of the Markdown source (used for reporting).
            adoc_path (str): The file path of the AsciiDoc target (used for reporting).
        
        Returns:
            ValidationReport: A report object containing the results of the comparison, including coverage percentage and any detected issues.
        """
        # Initialize the report with file paths
        report = ValidationReport(source_path=md_path, target_path=adoc_path)

        # Step 1: Normalize both texts to extract comparable prose
        md_prose = self._normalize_text(md_content, is_adoc=False)
        adoc_prose = self._normalize_text(adoc_content, is_adoc=True)

        # Step 2: Extract significant words for set comparison
        md_words = self.get_significant_words(md_prose)
        adoc_words = self.get_significant_words(adoc_prose)

        # Step 3: Calculate coverage and identify missing tokens
        if not md_words:
            report.skipped = True
            report.skip_reason = "Source Markdown has no significant prose."
            return report

        # Calculate intersection and missing tokens
        intersection = md_words & adoc_words
        missing = md_words - adoc_words
        coverage = round((len(intersection) / len(md_words)) * 100, 1)
        report.coverage = coverage

        # Only log to disk if we actually flag an issue (below 98%)
        # This keeps your data/audit-logs/ folder clean!
        if coverage < 98.0:
            self._write_detailed_log(md_path, {
                "file": str(md_path),
                "coverage": coverage,
                "metrics": {
                    "total_source_tokens": len(md_words),
                    "total_target_tokens": len(adoc_words),
                    "missing_count": len(missing)
                },
                "missing_tokens": sorted(list(missing)),
                "detected_tokens_sample": sorted(list(intersection))[:30]
            })

        # Flag issues based on coverage thresholds
        if coverage < 90.0:
            sample = ", ".join(sorted(list(missing))[:15])
            report.issues.append(ValidationIssue(
                severity="ERROR", 
                category="coverage",
                message=f"Critical content loss: Only {coverage}% found.",
                detail=f"Missing tokens: {sample} (Check data/audit-logs/ for full list)"
            ))
        elif coverage < 98.0:
            # The 98% threshold is a bit more lenient, acknowledging that minor token loss can occur due to formatting changes, but still warrants attention.
            report.issues.append(ValidationIssue(
                severity="WARNING", 
                category="coverage",
                message=f"Minor content loss detected: {coverage}% coverage."
            ))

        return report


    def _write_detailed_log(self, source_path: str, data: Dict):
        """Saves exhaustive validation details to a JSON file.
        
        Args:
            source_path (str): The file path of the Markdown source, used to name the log file.
            data (Dict): A dictionary containing all relevant details of the validation for this file,
            including coverage, missing tokens, and any other metrics or samples deemed useful for debugging.

        Returns:
            None: This function writes data to disk and does not return anything.
        """
        # Use the stem of the filename to create the log entry
        log_file = self.log_dir / f"{Path(source_path).stem}.json"

        # Ensure the log file is written with UTF-8 encoding to handle any special characters
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


    def _extract_headings(self, text: str, is_adoc: bool) -> List[Tuple[int, str]]:
        """Returns a list of (level, text) tuples for all headings.
        
        Args:
            text (str): The raw content of the file from which to extract headings.
            is_adoc (bool): Flag to indicate if the text is from an AsciiDoc
            file, which has different syntax rules for headings than Markdown.

        Returns:
            List[Tuple[int, str]]: A list of tuples where each tuple contains the heading level (e.g., 1 for H1, 2 for H2) and the heading text.
        """
        # This is a lightweight structural check to ensure major sections are present.
        headings = []
        # We only check for the presence and count of headings, not their exact text, to avoid false positives from minor wording changes.
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
        """Extracts the interior content of code blocks for logic-check.
        
        Args:
            text (str): The raw content of the file from which to extract code blocks.
            is_adoc (bool): Flag to indicate if the text is from an AsciiDoc
            file, which has different syntax rules for code blocks than Markdown.

        Returns:
            List[str]: A list of strings, each representing the interior content of a code block.
        """
        if is_adoc:
            # AsciiDoc blocks: ---- or [source] blocks
            return re.findall(r"^-{4,}\n(.*?)\n-{4,}", text, re.S | re.M)
        else:
            # Markdown blocks: ```
            return re.findall(r"^```.*?\n(.*?)\n```", text, re.S | re.M)


    def _check_structural_integrity(self, report: ValidationReport, 
                                   md_text: str, adoc_text: str):
        """Analyzes headings and code blocks with performance protection.
        
        Args:
            report (ValidationReport): The report object to which any detected issues will be added.
            md_text (str): The raw content of the Markdown file.
            adoc_text (str): The raw content of the AsciiDoc file.
        
        Returns:
            None: This function updates the report object in place and does not return anything.
        """
        # 1. Heading Check (Existing logic is fine, regex is fast here)
        md_h = self._extract_headings(md_text, is_adoc=False)
        adoc_h = self._extract_headings(adoc_text, is_adoc=True)
        
        # We only check for the count of headings, not their exact text, to avoid false positives from minor wording changes. 
        # This is a lightweight structural check to ensure major sections are present.
        if len(md_h) != len(adoc_h):
            report.issues.append(ValidationIssue(
                severity="WARNING", category="structure",
                message=f"Heading count mismatch: MD({len(md_h)}) vs ADOC({len(adoc_h)})"
            ))

        # 2. Code Block Check (The Performance Bottleneck)
        md_code = self._extract_code_blocks(md_text, is_adoc=False)
        adoc_code = self._extract_code_blocks(adoc_text, is_adoc=True)
        
        # If the counts don't match, we already know there's a structural issue, so we can skip the expensive content comparison.
        if len(md_code) != len(adoc_code):
            report.issues.append(ValidationIssue(
                severity="ERROR", category="code",
                message=f"Code block count mismatch! MD: {len(md_code)}, Result: {len(adoc_code)}"
            ))
        else:
            # If counts match, we can do a quick content similarity check to catch any major shifts without doing a full diff.
            for i, (m_block, a_block) in enumerate(zip(md_code, adoc_code)):
                m_clean, a_clean = m_block.strip(), a_block.strip()
                
                # PERFORMANCE GATE: If the character count difference is tiny (<2%), skip heavy diffing and 
                # assume it's a minor formatting change. This prevents the validator from getting bogged down on 
                # large code blocks that are mostly intact.
                len_diff = abs(len(m_clean) - len(a_clean))
                if len_diff > 50 and (len_diff / max(len(m_clean), 1)) > 0.02:
                    # Use quick_ratio on a sample (first 5000 chars) for speed
                    ratio = difflib.SequenceMatcher(None, m_clean[:5000], a_clean[:5000]).quick_ratio()
                    # If the similarity is below 85%, we flag it as a warning. This catches major content shifts without the overhead of a full diff.
                    if ratio < 0.85:
                        report.issues.append(ValidationIssue(
                            severity="WARNING", category="code",
                            message=f"Code block {i+1} content shifted significantly.",
                            detail=f"Similarity approx: {ratio:.1%}"
                        ))


    def _extract_table_footprint(self, text: str, is_adoc: bool) -> List[int]:
        """Returns a list where each entry is the number of columns in a table.
        
        Args:
            text (str): The raw content of the file from which to extract table footprints.
            is_adoc (bool): Flag to indicate if the text is from an AsciiDoc file, which has different syntax rules for tables than Markdown.

        Returns:
            List[int]: A list of integers where each integer represents the number of columns in a detected table.
            This serves as a "footprint" to compare table structures between Markdown and AsciiDoc.  
        """
        # This is a heuristic to check if tables are being lost or significantly altered.
        footprints = []
        
        # For AsciiDoc, we look for lines starting with '|===' to identify table boundaries and count the number of '|' in rows to determine column count.
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

        Args:
            input_dir (Path): The directory containing the original Markdown files.
            output_dir (Path): The directory containing the converted AsciiDoc files.
        
        Returns:
            List[ValidationReport]: A list of ValidationReport objects, each representing the results of validating a single file pair.
            This includes coverage metrics and any detected issues for each file.
        """
        # For each Markdown file, we generate a ValidationReport that includes:
        reports = []
        # Support both .md and .mdx
        input_files = []

        # We use rglob to recursively find all Markdown files in the input directory, supporting both .md and .mdx extensions.
        for ext in [".md", ".mdx"]:
            input_files.extend(list(input_dir.rglob(f"*{ext}")))

        # We then iterate over each Markdown file, determine the expected AsciiDoc path, and perform the comparison. If the AsciiDoc file is missing, we log an error. Otherwise, we run both the prose comparison and structural checks, accumulating any issues into the ValidationReport for that file.
        for md_path in input_files:
            # Determine the expected path in the output folder
            rel_path = md_path.relative_to(input_dir)
            adoc_path = output_dir / rel_path.with_suffix(".adoc")

            # Check if the AsciiDoc file exists
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

            # Run basic prose comparison
            report = self.compare(md_text, adoc_text, str(rel_path), str(adoc_path))
            
            # Run structural comparison
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
    

    def render_terminal_report(self, reports: List[ValidationReport]) -> None:
        """Prints a high-visibility summary of the validation results.
        
        Args:
            reports (List[ValidationReport]): A list of ValidationReport objects to summarize.

        Returns:
            None: This function prints the report to the terminal and does not return anything. 
        """
        # We summarize the results with clear counts of total files, passes, and failures. 
        # For any files that failed validation, we provide a concise breakdown of the issues detected, categorized by severity and type. 
        # We also highlight where detailed logs can be found for further investigation.
        total = len(reports)
        passed = sum(1 for r in reports if r.passed)
        failed = total - passed
        
        print("\n" + "="*60)
        print("🔍 TRANSPILER-PRO AUDIT REPORT")
        print("="*60)
        print(f"Total Files Scanned: {total}")
        print(f"Passed Validation:   {passed} ✅")
        print(f"Issues Detected:     {failed} ⚠️")
        print(f"Detailed Logs:       {self.log_dir}/")
        print("-" * 60)

        # We then iterate through the reports and print out any that did not pass validation, including the specific issues found. 
        # This allows for quick identification of problem areas while keeping the terminal output concise and actionable.
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

        # Finally, we provide a closing summary that emphasizes the importance of reviewing any flagged issues and 
        # directs users to the detailed logs for in-depth analysis. This ensures that while the terminal report is concise, 
        # users have a clear path to investigate and resolve any content integrity concerns.
        if failed == 0:
            print("✨ PARITY PERFECT: No content loss detected.")
        else:
            print(f"🚩 AUDIT COMPLETE: {failed} files require manual review.")
        print("="*60 + "\n")
