"""Location: src/transpiler_pro/core/fixer.py
Description: Learning-capable StyleFixer. Uses an external JSON Knowledge Base
and a Global Enforcement Pass to ensure enterprise standards are always met.
"""

import re
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import spacy

class StyleFixer:
    """Dynamic repair logic driven by Linter suggestions and a JSON Knowledge Base."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_config()
        
        # Load the Knowledge Base (JSON)
        kb_setting = self.config.get("pipeline", {}).get("knowledge_base", "data/knowledge_base.json")
        self.kb_path = Path(kb_setting)
        self.kb = self._load_kb()

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

    def _load_kb(self) -> dict:
        """Loads the external JSON brain."""
        if self.kb_path.exists():
            try:
                return json.loads(self.kb_path.read_text())
            except:
                pass
        return {"branding": {}, "learned": {}}

    def _save_kb(self) -> None:
        """Persists learned words back to the JSON file."""
        self.kb_path.parent.mkdir(parents=True, exist_ok=True)
        self.kb_path.write_text(json.dumps(self.kb, indent=4), encoding="utf-8")

    def _get_progressive_verb(self, verb_token) -> str:
        """Prioritizes TOML special_verbs to ensure accuracy over algorithm."""
        lemma = verb_token.lemma_.lower()
        grammar_cfg = self.config.get("grammar", {})
        special = grammar_cfg.get("special_verbs", {})
        if lemma in special:
            return special[lemma]

        if lemma.endswith("e") and not lemma.endswith("ee"):
            return lemma[:-1] + "ing"
        if len(lemma) > 2 and lemma[-1] not in "aeiou" and lemma[-2] in "aeiou" and lemma[-3] not in "aeiou":
            return lemma + lemma[-1] + "ing"
        return lemma + "ing"

    def _fix_tense(self, line: str) -> str:
        if not self.nlp: return line
        doc = self.nlp(line)
        working_line = line
        for token in doc:
            if token.text.lower() == "will":
                main_verb = token.head
                if main_verb.pos_ == "VERB":
                    subjects = [w for w in main_verb.lefts if "subj" in w.dep_]
                    is_plural = any("Number=Plur" in str(s.morph) or s.text.lower() in ["we", "they", "you"] for s in subjects)
                    aux = "are" if is_plural else "is"
                    prog = self._get_progressive_verb(main_verb)
                    working_line = re.sub(rf"\b{token.text}\s+{main_verb.text}\b", f"{aux} {prog}", working_line, flags=re.IGNORECASE)
        return working_line

    def fix_file(self, file_path: Path, violations: List[Dict[str, Any]]) -> int:
        if not file_path.exists(): return 0
        content = file_path.read_text(encoding="utf-8").splitlines()
        total_fixes = 0
        
        line_map = defaultdict(list)
        for v in violations: line_map[v["Line"]].append(v)

        patterns = self.config.get("patterns", {})
        extract_re = patterns.get("suggestion_extraction", r"'(.*?)'")
        remove_trigger = patterns.get("removal_trigger", "removing")

        # Combine branding and learned words for high-priority matching
        session_branding = {**self.kb.get("learned", {}), **self.kb.get("branding", {})}

        for line_num in sorted(line_map.keys(), reverse=True):
            idx = line_num - 1
            if idx >= len(content): continue
            
            working_line = content[idx]
            original_line = working_line

            # --- PHASE A: LINTER-DRIVEN REPAIRS ---
            for issue in line_map[line_num]:
                msg = issue.get("Message", "")
                check_id = issue.get("Check", "")

                # 1. BRANDING (Linter-flagged)
                for wrong, correct in session_branding.items():
                    if f"'{wrong}'" in msg.lower() or f"‘{wrong}’" in msg.lower():
                        working_line = re.sub(rf"\b{re.escape(wrong)}\b", correct, working_line, flags=re.IGNORECASE)

                # 2. SURGICAL REMOVAL (e.g., 'very')
                if remove_trigger in msg.lower():
                    targets = re.findall(extract_re, msg)
                    if targets:
                        working_line = re.sub(rf"\b{re.escape(targets[0])}\b\s?", "", working_line, flags=re.IGNORECASE)

                # 3. PHRASAL SUBSTITUTION
                elif "instead of" in msg.lower():
                    terms = re.findall(extract_re, msg)
                    if len(terms) >= 2:
                        working_line = re.sub(rf"\b{re.escape(terms[1])}\b", terms[0], working_line, flags=re.IGNORECASE)

                # 4. SPELLING + LEARNING DISCOVERY
                elif "Spelling" in check_id:
                    targets = re.findall(extract_re, msg)
                    if targets:
                        word = targets[0]
                        if word.lower() not in session_branding:
                            capitalized = word.capitalize()
                            working_line = re.sub(rf"\b{re.escape(word)}\b", capitalized, working_line, flags=re.IGNORECASE)
                            # Discovery Log
                            if word.lower() not in self.kb["branding"]:
                                self.kb["learned"][word.lower()] = capitalized

                # 5. TENSE SHIFT
                if check_id == "common.Will":
                    working_line = self._fix_tense(working_line)

            # --- PHASE B: GLOBAL ENFORCEMENT PASS ---
            # Safety net: Fix known branding even if linter missed it (e.g., 'id' -> 'ID')
            for wrong, correct in self.kb.get("branding", {}).items():
                if re.search(rf"\b{re.escape(wrong)}\b", working_line, flags=re.IGNORECASE):
                    # We only replace if it's not already exactly correct
                    working_line = re.sub(rf"\b{re.escape(wrong)}\b", correct, working_line)

            if working_line != original_line:
                content[idx] = working_line
                total_fixes += 1

        file_path.write_text("\n".join(content), encoding="utf-8")
        self._save_kb() 
        return total_fixes