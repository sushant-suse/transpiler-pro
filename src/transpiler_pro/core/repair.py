"""
Location: src/transpiler_pro/core/repair.py
Description: Linguistic Repair Engine for Transpiler-Pro.
"""

import spacy
import re
from pathlib import Path

# Load the NLP model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class LinguisticEngine:
    def __init__(self, knowledge_base: dict):
        # Explicitly target automated_fixes to prevent 'learned' categories leaking in
        self.kb = knowledge_base.get("automated_fixes", {})

    def repair_text(self, text: str) -> str:
        """Runs the full linguistic healing pipeline."""
        
        # 1. Branding & High-Confidence Fixes
        # We sort by length descending so "Wi-Fi Settings" is fixed before "Wi-Fi"
        sorted_errors = sorted(self.kb.keys(), key=len, reverse=True)
        
        for error in sorted_errors:
            fix = self.kb[error]
            # SAFETY: If the fix value is "spellings", it's a category name, not a fix. Skip it.
            if fix.lower() == "spellings":
                continue
                
            # \b ensures we only match whole words
            text = re.sub(rf"\b{re.escape(error)}\b", fix, text, flags=re.IGNORECASE)

        # 2. NLP Tense Shifting (Future -> Active Present)
        doc = nlp(text)
        corrected_text = text
        
        # Track replacements to prevent string offset issues
        replacements = {}

        for token in doc:
            # Detect Future Auxiliaries (will, shall) attached to a Verb
            if token.dep_ == "aux" and token.lemma_.lower() in ["will", "shall"]:
                verb = token.head
                if verb.pos_ in ["VERB", "AUX"]:
                    # Create the phrase found in text (e.g., "will setup")
                    future_phrase = f"{token.text} {verb.text}"
                    present_verb = self._conjugate_to_present(verb)
                    
                    # Map the specific phrase to its conjugated form
                    replacements[future_phrase] = present_verb
        
        # Apply NLP replacements using regex for word boundary safety
        for future, present in replacements.items():
            corrected_text = re.sub(rf"\b{re.escape(future)}\b", present, corrected_text)
            
        return corrected_text

    def _conjugate_to_present(self, verb_token) -> str:
        """
        Conjugates a verb to 3rd person singular present.
        Example: verify -> verifies, support -> supports, be -> is.
        """
        lemma = verb_token.lemma_.lower()
        
        # 1. Special case: 'be' (will be -> is)
        if lemma == "be":
            return "is"
        
        # 2. Rule: Consonant + 'y' -> 'ies' (verify -> verifies)
        # Check that there is a character before 'y' and it's not a vowel
        if lemma.endswith("y") and len(lemma) > 1 and lemma[-2] not in "aeiou":
            return lemma[:-1] + "ies"
        
        # 3. Rule: Sibilant endings -> 'es' (fix -> fixes, watch -> watches, brush -> brushes)
        if lemma.endswith(("s", "sh", "ch", "x", "z")):
            return lemma + "es"
            
        # 4. Standard Rule: + 's' (support -> supports)
        return lemma + "s"