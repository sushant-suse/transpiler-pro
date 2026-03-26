"""
Location: src/transpiler_pro/core/fixer.py
Description: The Style Fixer and "Auto-Heal" Engine.

This module provides the `StyleFixer` class, which is responsible for taking 
the violations found by the StyleLinter and applying surgical corrections.

It employs three distinct repair strategies:
1. Linter-Driven: Directly resolving issues flagged by Vale (spelling, wordiness).
2. Knowledge Base: Enforcing branding and technical terms from a JSON brain.
3. Global Guardrails: Applying safety-first regex to ensure consistency across 
   prose without breaking technical syntax (URLs, paths, macros).
"""

import re
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import spacy
from rich.console import Console

console = Console()

class StyleFixer:
    """
    NLP-enhanced repair engine that learns and persists style corrections.
    
    Attributes:
        config (Dict): Tool configuration extracted from pyproject.toml.
        kb_path (Path): Location of the persistent JSON knowledge base.
        kb (Dict): The internal memory of the fixer (Branding + Learned terms).
        nlp: The spaCy language model used for linguistic context checks.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initializes the fixer and loads the persistent Knowledge Base.
        
        Args:
            config_path (Path, optional): Custom path to pyproject.toml.
        """
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_config()
        
        # Load the Knowledge Base (JSON) which stores branding and learned words.
        kb_setting = self.config.get("pipeline", {}).get("knowledge_base", "data/knowledge_base.json")
        self.kb_path = Path(kb_setting)
        self.kb = self._load_kb()

        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception:
            # Fallback if spaCy is missing; some tense-shifting features may be limited.
            self.nlp = None

    def _load_config(self) -> Dict[str, Any]:
        """Reads the [tool.transpiler-pro] section from the project TOML."""
        if not self.config_path.exists(): 
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except (tomllib.TOMLDecodeError, OSError):
            return {}

    def _load_kb(self) -> Dict[str, Any]:
        """Loads the JSON brain. Initializes empty branding/learned dicts if missing."""
        if self.kb_path.exists():
            try:
                return json.loads(self.kb_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"branding": {}, "learned": {}}

    def _save_kb(self) -> None:
        """Persists learned corrections to disk for future pipeline runs."""
        try:
            self.kb_path.parent.mkdir(parents=True, exist_ok=True)
            self.kb_path.write_text(json.dumps(self.kb, indent=4), encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Error saving Knowledge Base:[/] {e}")

    def _get_progressive_verb(self, verb_token) -> str:
        """
        Logic to convert a verb to its '-ing' form.
        
        Prioritizes the 'special_verbs' table in pyproject.toml to handle 
        irregular conjugations (e.g., 'stop' -> 'stopping') before falling 
        back to standard English suffix rules.
        """
        lemma = verb_token.lemma_.lower()
        grammar_cfg = self.config.get("grammar", {})
        special = grammar_cfg.get("special_verbs", {})
        
        if lemma in special:
            return special[lemma]

        # Standard -ing rules
        if lemma.endswith("e") and not lemma.endswith("ee"):
            return lemma[:-1] + "ing"
        # CVC rule: Double the consonant (e.g., run -> running)
        if len(lemma) > 2 and lemma[-1] not in "aeiou" and lemma[-2] in "aeiou" and lemma[-3] not in "aeiou":
            return lemma + lemma[-1] + "ing"
        return lemma + "ing"

    def _fix_tense(self, line: str) -> str:
        """
        Standard Tense Shifter: "We will test" -> "We are testing".
        Note: This is an legacy/alternative shifter; primary tense shifting 
        is now handled by the more advanced LinguisticEngine in repair.py.
        """
        if not self.nlp: 
            return line
        doc = self.nlp(line)
        working_line = line
        for token in doc:
            if token.text.lower() == "will":
                main_verb = token.head
                if main_verb.pos_ == "VERB":
                    # Determine plurality for correct aux verb (is vs are)
                    subjects = [w for w in main_verb.lefts if "subj" in w.dep_]
                    is_plural = any("Number=Plur" in str(s.morph) or s.text.lower() in ["we", "they", "you"] for s in subjects)
                    aux = "are" if is_plural else "is"
                    prog = self._get_progressive_verb(main_verb)
                    working_line = re.sub(rf"\b{token.text}\s+{main_verb.text}\b", f"{aux} {prog}", working_line, flags=re.IGNORECASE)
        return working_line

    def fix_file(self, file_path: Path, violations: List[Dict[str, Any]]) -> int:
        """
        The main repair loop. Iterates through line-specific violations and 
        applies branding and style corrections.

        Args:
            file_path (Path): Path to the generated AsciiDoc file.
            violations (List[Dict]): List of findings from the Linter.
            
        Returns:
            int: Number of lines successfully modified.
        """
        if not file_path.exists(): 
            return 0
        content = file_path.read_text(encoding="utf-8").splitlines()
        total_fixes = 0
        
        # Group issues by line number for efficient processing
        line_map = defaultdict(list)
        for v in violations: 
            line_map[v.get("Line", 0)].append(v)

        patterns = self.config.get("patterns", {})
        extract_re = patterns.get("suggestion_extraction", r"'(.*?)'")
        remove_trigger = patterns.get("removal_trigger", "removing")
        instead_of_trigger = patterns.get("instead_of_trigger", "instead of")

        # Current branding context (Permanent + Learned during this session)
        session_branding = {**self.kb.get("learned", {}), **self.kb.get("automated_fixes", {})}

        # Process lines in reverse order to ensure line-length changes don't shift indices
        for line_num in sorted(line_map.keys(), reverse=True):
            idx = line_num - 1
            if idx < 0 or idx >= len(content): 
                continue
            
            working_line = content[idx]
            original_line = working_line

            # --- PHASE 1: LINTER-DRIVEN REPAIRS ---
            for issue in line_map[line_num]:
                msg = issue.get("Message", "")
                check_id = issue.get("Check", "")
                suggestion = issue.get("Suggestion", "")

                # 1. Branding Sync (e.g., Use 'SUSE' instead of 'suse')
                for wrong, correct in session_branding.items():
                    if f"'{wrong}'" in msg.lower() or f"‘{wrong}’" in msg.lower():
                        working_line = re.sub(rf"\b{re.escape(wrong)}\b", correct, working_line, flags=re.IGNORECASE)

                # 2. Surgical Removal (e.g., "Note that...", "Actually...")
                if remove_trigger in msg.lower() or "Editorializing" in check_id:
                    target = suggestion if suggestion else (re.findall(extract_re, msg)[0] if re.findall(extract_re, msg) else None)
                    if target:
                        working_line = re.sub(rf"\b{re.escape(target)}\b\s?", "", working_line, flags=re.IGNORECASE)

                # 3. Phrasal Substitution (e.g., "Use 'X' instead of 'Y'")
                elif instead_of_trigger in msg.lower():
                    if suggestion:
                        m = re.findall(extract_re, msg)
                        wrong_term = m[1] if len(m) >= 2 else (m[0] if m else "")
                        if wrong_term:
                            # --- GUARDRAIL: Let repair.py handle complex tense shifts ---
                            if "will" in wrong_term.lower() or "will" in msg.lower():
                                continue
                            working_line = re.sub(rf"\b{re.escape(wrong_term)}\b", suggestion, working_line, flags=re.IGNORECASE)

                # 4. Auto-Learning: Capture spelling fixes into the Knowledge Base
                elif "Spelling" in check_id:
                    if suggestion and suggestion.lower() not in ["spelling", "spellings", "learned"]:
                        match = re.findall(extract_re, msg)
                        word_to_fix = match[0] if match else ""
                        if word_to_fix:
                            working_line = re.sub(rf"\b{re.escape(word_to_fix)}\b", suggestion, working_line)
                            # Persist this correction for future automation
                            if word_to_fix.lower() not in session_branding:
                                self.kb["learned"][word_to_fix.lower()] = suggestion

            # --- PHASE 2: GLOBAL BRANDING & FORMATTING GUARDRAILS ---
            
            # 1. Branding Guardrail: Apply core branding safely (no URL/Path corruption)
            for wrong, correct in self.kb.get("automated_fixes", {}).items():
                # Negative lookarounds (?<![\/-]) prevent breaking paths like /img/suse-logo.svg
                pattern = rf"(?<![\/-])\b{re.escape(wrong)}\b(?![\/-])"
                working_line = re.sub(pattern, correct, working_line, flags=re.IGNORECASE)

            # 2. Fragment Healer: Ensure sentences start with capital letters
            # Ignores lines starting with AsciiDoc technical syntax
            if not re.match(r'^(image::|video::|xref:|link:|http|\[|:)', working_line, flags=re.IGNORECASE):
                working_line = re.sub(r'(^|\.\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), working_line)

            # Update line in content if modifications were made
            if working_line != original_line:
                content[idx] = working_line
                total_fixes += 1

        # Write corrected content back and update the JSON brain
        file_path.write_text("\n".join(content), encoding="utf-8")
        self._save_kb() 
        return total_fixes