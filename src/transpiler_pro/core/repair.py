import spacy
import re
from spacy.util import filter_spans

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
        
        # --- FIX A: HYPHEN MERGER (Safe for dates and multi-hyphens) ---
        spans_to_merge = []
        for token in doc:
            if token.text == "-" and token.i > 0 and token.i < len(doc) - 1:
                spans_to_merge.append(doc[token.i - 1 : token.i + 2])
                
        with doc.retokenize() as retokenizer:
            for span in filter_spans(spans_to_merge):
                retokenizer.merge(span)
        
        tense_map = {}
        
        for token in doc:
            if token.pos_ == "VERB":
                auxiliaries = [w.lemma_.lower() for w in token.lefts if w.dep_ in ["aux", "auxpass"]]
                if "have" in auxiliaries:
                    continue

            # --- FINAL BOSS: SIMPLIFIED SUBJECT & TENSE SHIFTER ---
            if token.pos_ == "AUX" and token.lemma_ == "will":
                
                # Look ahead to see if the next word is "be" (Passive Voice or Progressive)
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                is_passive_or_progressive = next_token and next_token.lemma_ == "be"
                
                # Determine the true subject by looking backwards in the sentence
                # This bypasses spaCy's complex dependency tree failures
                subject_token = None
                for j in range(token.i - 1, -1, -1):
                    if doc[j].pos_ in ["PRON", "NOUN", "PROPN"]:
                        subject_token = doc[j]
                        break
                
                # Determine Plurality based on the subject we found
                is_plural = False
                if subject_token:
                    t = subject_token.text.lower()
                    if t in ["you", "we", "i", "they"]:
                        is_plural = True
                    elif subject_token.tag_ in ["NNS", "NNPS"] or "Number=Plur" in str(subject_token.morph):
                        is_plural = True
                    elif t.endswith('s') and t not in ["status", "process", "this", "us", "analysis", "address", "class"]:
                        is_plural = True

                # SCENARIO A: "will be" -> "is/are"
                if is_passive_or_progressive:
                    replacement = "are" if is_plural else "is"
                    pattern = rf"(?i)\b{token.text}\s+{re.escape(next_token.text)}\b"
                    tense_map[pattern] = replacement

                # SCENARIO B: "will [verb]" -> "[verb]s"
                else:
                    head = token.head
                    if head.pos_ in ["VERB", "AUX", "NOUN", "ADJ"] and head != token:
                        if "-" in head.text:
                            replacement = head.text if is_plural else f"{head.text}s"
                        elif is_plural:
                            replacement = head.text
                        else:
                            replacement = self._conjugate_to_present(head)
                            
                        pattern = rf"(?i)\b{token.text}\s+{re.escape(head.text)}\b"
                        tense_map[pattern] = replacement

        for phrase, replacement in tense_map.items():
            text = re.sub(phrase, replacement, text)

        for i, original_content in enumerate(protected_blocks):
            text = text.replace(f"REPAIR_SHIELD_{i}_", original_content)

        return text

    def _conjugate_to_present(self, verb_token) -> str:
        text = verb_token.text
        if text.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return text + "es"
        elif text.endswith('y') and len(text) > 1 and text[-2] not in "aeiou":
            return text[:-1] + "ies"
        else:
            return text + "s" # Properly handles "execute" -> "executes"