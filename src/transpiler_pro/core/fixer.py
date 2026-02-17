"""Location: src/transpiler_pro/core/fixer.py
Description: Purely dynamic StyleFixer. Does not contain any hardcoded branding or 
mappings. It relies entirely on linter-provided suggestions and generic NLP rules.
"""

import re
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import spacy

class StyleFixer:
    """The 'Dumb' Engine: It only knows HOW to fix, not WHAT to fix."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_config()
        
        # Load NLP for structural shifts (Will -> Present Progressive)
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            self.nlp = None

    def _load_config(self) -> dict:
        if not self.config_path.exists(): return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except: return {}

    def _get_progressive_verb(self, verb_token) -> str:
        """Dynamic morphological transformation using standard linguistic rules."""
        lemma = verb_token.lemma_.lower()
        # Basic English rules; could be further externalized to a grammar file
        if lemma.endswith("e") and not lemma.endswith("ee"):
            return lemma[:-1] + "ing"
        # CVC doubling logic
        if len(lemma) > 2 and lemma[-1] not in "aeiou" and lemma[-2] in "aeiou" and lemma[-3] not in "aeiou":
            return lemma + lemma[-1] + "ing"
        return lemma + "ing"

    def _fix_tense(self, line: str) -> str:
        """NLP-driven transformation based on structural analysis."""
        if not self.nlp: return line
        doc = self.nlp(line)
        working_line = line
        for token in doc:
            if token.text.lower() == "will":
                main_verb = token.head
                if main_verb.pos_ == "VERB":
                    # Determine auxiliary based on subject
                    subjects = [w for w in main_verb.lefts if "subj" in w.dep_]
                    is_plural = any("Number=Plur" in str(s.morph) or s.text.lower() in ["we", "they", "you"] for s in subjects)
                    aux = "are" if is_plural else "is"
                    prog = self._get_progressive_verb(main_verb)
                    working_line = re.sub(rf"\b{token.text}\s+{main_verb.text}\b", f"{aux} {prog}", working_line, flags=re.IGNORECASE)
        return working_line

    def fix_file(self, file_path: Path, violations: List[Dict[str, Any]]) -> int:
        """
        Executes fixes purely based on what the Linter (Vale) found.
        If Vale says suse -> SUSE, we do it. We don't maintain our own list.
        """
        if not file_path.exists(): return 0
        content = file_path.read_text(encoding="utf-8").splitlines()
        total_fixes = 0
        
        # Map violations to lines for atomic processing
        line_map = defaultdict(list)
        for v in violations: line_map[v["Line"]].append(v)

        # Dynamic Extraction Patterns from TOML
        patterns = self.config.get("patterns", {})
        extract_re = patterns.get("suggestion_extraction", r"'(.*?)'")

        for line_num in sorted(line_map.keys(), reverse=True):
            idx = line_num - 1
            if idx >= len(content): continue
            line = content[idx]
            original = line

            for issue in line_map[line_num]:
                msg = issue.get("Message", "")
                suggestion = issue.get("Suggestion")

                # 1. DIRECT REPLACEMENT: Linter provided a 'Suggestion' field
                if suggestion:
                    # Find the 'wrong' word in the message to replace in the text
                    # e.g., "Did you mean 'SUSE' instead of 'suse'?"
                    wrong_terms = re.findall(extract_re, msg)
                    target = wrong_terms[-1] if wrong_terms else None
                    if target:
                        line = re.sub(rf"\b{target}\b", suggestion, line, flags=re.IGNORECASE)

                # 2. PHRASAL SUBSTITUTION: Linter didn't provide field, but msg has terms
                # e.g., "Consider using 'configuration' instead of 'config'"
                elif "instead of" in msg.lower():
                    terms = re.findall(extract_re, msg)
                    if len(terms) >= 2:
                        line = re.sub(rf"\b{terms[1]}\b", terms[0], line, flags=re.IGNORECASE)

                # 3. SURGICAL REMOVAL:
                # e.g., "Consider removing 'very'"
                elif "removing" in msg.lower():
                    terms = re.findall(extract_re, msg)
                    if terms:
                        line = re.sub(rf"\b{terms[0]}\b\s?", "", line, flags=re.IGNORECASE)

                # 4. TENSE SHIFTING:
                if issue.get("Check") == "common.Will":
                    line = self._fix_tense(line)

            if line != original:
                content[idx] = line
                total_fixes += 1

        file_path.write_text("\n".join(content), encoding="utf-8")
        return total_fixes