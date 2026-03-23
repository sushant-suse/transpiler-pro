"""
Location: src/transpiler_pro/core/repair.py
Description: Advanced Dynamic Linguistic Repair Engine.
Enhanced with Code Block Shielding to prevent accidental 'repairs' to source code.
"""
import spacy
import re
from typing import Dict, Any, List

# Load spaCy
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class LinguisticEngine:
    def __init__(self, knowledge_base: dict):
        """Initializes the engine with a restricted view of the knowledge base."""
        # Audit Finding: Explicitly isolate automated_fixes to prevent 'spellings' leak.
        self.kb = knowledge_base.get("automated_fixes", {})

    def repair_text(self, text: str) -> str:
        """Heals text using whitespace-agnostic lookarounds and modal-verb collapsing."""
        
        # --- NEW: CODE BLOCK SHIELDING ---
        # We protect content inside [source] blocks or between ---- delimiters
        protected_blocks = []
        def shield_code(match):
            placeholder = f"REPAIR_SHIELD_{len(protected_blocks)}_"
            protected_blocks.append(match.group(0))
            return placeholder

        # Shield AsciiDoc source blocks
        text = re.sub(r'(\[source,.*?\]\n----\n(.*?)\n----)', shield_code, text, flags=re.DOTALL)

        # --- PASS 1: Aggressive Branding ---
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            if str(replacement).lower() in ["spellings", "learned", "none"]:
                continue
            
            pattern = rf"(?i)(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])"
            text = re.sub(pattern, replacement, text)

        # --- PASS 2: Recursive NLP Tense Shift ---
        doc = nlp(text)
        tense_map = {}
        
        for token in doc:
            if token.pos_ == "AUX" and token.dep_ == "aux":
                head = token.head
                if head.pos_ in ["VERB", "AUX", "ADJ"]:
                    # Phrase regex handling potential whitespace variations
                    phrase_regex = rf"{re.escape(token.text)}\s+{re.escape(head.text)}"
                    present_form = self._conjugate_to_present(head)
                    tense_map[phrase_regex] = present_form

        for phrase, replacement in tense_map.items():
            text = re.sub(rf"(?i)(?<![a-zA-Z0-9]){phrase}(?![a-zA-Z0-9])", replacement, text)

        # --- RESTORE PROTECTED BLOCKS ---
        for i, original_content in enumerate(protected_blocks):
            text = text.replace(f"REPAIR_SHIELD_{i}_", original_content)

        return text

    def _conjugate_to_present(self, token) -> str:
        """Morphological Conjugation for 3rd-person singular technical instructions."""
        lemma = token.lemma_.lower()
        
        irregulars = {"be": "is", "have": "has", "do": "does", "go": "goes"}
        if lemma in irregulars:
            return irregulars[lemma]
        
        # Rules for -s, -sh, -ch, -x, -z
        if lemma.endswith(("s", "sh", "ch", "x", "z")):
            return lemma + "es"
        
        # Rules for consonant + y
        if lemma.endswith("y") and len(lemma) > 1 and lemma[-2] not in "aeiou":
            return lemma[:-1] + "ies"
        
        return lemma + "s"