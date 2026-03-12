"""
Location: src/transpiler_pro/core/repair.py
Description: Advanced Dynamic Linguistic Repair Engine.
Handles whitespace-agnostic branding and recursive dependency healing.
"""
import spacy
import re
from pathlib import Path

# Load spaCy
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class LinguisticEngine:
    def __init__(self, knowledge_base: dict):
        # Isolate ONLY automated_fixes to prevent the 'spellings' bug
        self.kb = knowledge_base.get("automated_fixes", {})

    def repair_text(self, text: str) -> str:
        """Heals text using whitespace-agnostic lookarounds and modal-verb collapsing."""
        
        # --- PASS 1: Aggressive Branding (Case Insensitive + Symbol Safe) ---
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            if replacement.lower() == "spellings": continue
            
            # Use Lookarounds: Match key if not preceded/followed by a letter or number
            # This catches 'wifi' in bullet points like '* wifi' flawlessly.
            pattern = rf"(?i)(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])"
            text = re.sub(pattern, replacement, text)

        # --- PASS 2: Recursive NLP Tense Shift ---
        doc = nlp(text)
        tense_map = {}
        
        for token in doc:
            # Detect ANY auxiliary (will, shall, should, must, etc.)
            if token.pos_ == "AUX" and token.dep_ == "aux":
                head = token.head
                # Catch "should be", "will verify", "must check"
                # head.pos_ can be VERB, AUX, or even ADJ in passive docs
                if head.pos_ in ["VERB", "AUX", "ADJ"]:
                    # Create phrase regex handling any amount of whitespace
                    phrase_regex = rf"{re.escape(token.text)}\s+{re.escape(head.text)}"
                    
                    # Generate the present tense form
                    present_form = self._conjugate_to_present(head)
                    tense_map[phrase_regex] = present_form

        # Apply tense replacements with boundary safety
        for phrase, replacement in tense_map.items():
            text = re.sub(rf"(?i)(?<![a-zA-Z0-9]){phrase}(?![a-zA-Z0-9])", replacement, text)

        return text

    def _conjugate_to_present(self, token) -> str:
        """Dynamic Morphological Conjugation for technical documentation."""
        lemma = token.lemma_.lower()
        
        # 1. irregulars common in technical instructions
        if lemma == "be": return "is"
        if lemma == "have": return "has"
        
        # 2. Dynamic Suffix Rules
        if lemma.endswith(("s", "sh", "ch", "x", "z")):
            return lemma + "es"
        if lemma.endswith("y") and len(lemma) > 1 and lemma[-2] not in "aeiou":
            return lemma[:-1] + "ies"
        
        return lemma + "s"