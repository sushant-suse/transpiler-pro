import spacy
import re

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class LinguisticEngine:
    def __init__(self, knowledge_base: dict):
        self.kb = knowledge_base.get("automated_fixes", {})

    def repair_text(self, text: str) -> str:
        protected_blocks = []
        def shield_code(match):
            placeholder = f"REPAIR_SHIELD_{len(protected_blocks)}_"
            protected_blocks.append(match.group(0))
            return placeholder

        text = re.sub(r'(\[source,.*?\]\n----\n(.*?)\n----)', shield_code, text, flags=re.DOTALL)

        # PASS 1: Aggressive Branding (Fixed to ignore rule-name corruption)
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            # Safety Check: Don't replace if replacement is empty, a rule-id, or the word 'spellings'
            if not replacement or str(replacement).lower() in ["spellings", "spelling", "learned", "none", "val"]:
                continue
            
            pattern = rf"(?i)(?<![a-zA-Z0-9/]){re.escape(key)}(?![a-zA-Z0-9])"
            text = re.sub(pattern, replacement, text)

        # PASS 2: Recursive NLP Tense Shift (Fixed for Subject Agreement)
        doc = nlp(text)
        tense_map = {}
        
        for token in doc:
            if token.pos_ == "VERB":
                auxiliaries = [w.lemma_.lower() for w in token.lefts if w.dep_ in ["aux", "auxpass"]]
                if "have" in auxiliaries:
                    continue
                
            # --- SURGICAL FIX: Subject-Aware Tense Shifting ---
            if token.pos_ == "AUX" and token.lemma_ == "will":
                head = token.head
                if head.pos_ in ["VERB", "AUX"]:
                    # 1. Grab ALL subjects (including 'nsubjpass' for passive voice!)
                    # This fixes the "You is prompted" bug.
                    subjects = [w for w in head.children if "subj" in w.dep_]
                    
                    # Also check the head's head in case of complex dependent clauses ("we reboots")
                    if not subjects and head.head != head:
                        subjects = [w for w in head.head.children if "subj" in w.dep_]
                        
                    is_user_subject = any(s.lemma_.lower() in ["you", "we", "i"] for s in subjects)
                    
                    # 2. Hyphenated Word Protection (Fixes "res-prompt")
                    if "-" in head.text:
                        replacement = head.text if is_user_subject else f"{head.text}s"
                    else:
                        # 3. Base form for User, Conjugated for System
                        if is_user_subject:
                            replacement = "are" if head.lemma_ == "be" else head.text
                        else:
                            replacement = self._conjugate_to_present(head)
                    
                    pattern = rf"(?i)\b{token.text}\s+{re.escape(head.text)}\b"
                    tense_map[pattern] = replacement

        for phrase, replacement in tense_map.items():
            text = re.sub(phrase, replacement, text)

        for i, original_content in enumerate(protected_blocks):
            text = text.replace(f"REPAIR_SHIELD_{i}_", original_content)

        return text

    def _conjugate_to_present(self, token) -> str:
        # Check if it's already at the start of a bullet or step (Keep Imperative)
        # We don't want "Step 1: Runs"
        lemma = token.lemma_.lower()
        irregulars = {"be": "is", "have": "has", "do": "does", "go": "goes"}
        if lemma in irregulars: return irregulars[lemma]
        if lemma.endswith(("s", "sh", "ch", "x", "z")): return lemma + "es"
        if lemma.endswith("y") and len(lemma) > 1 and lemma[-2] not in "aeiou": return lemma[:-1] + "ies"
        return lemma + "s"