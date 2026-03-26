"""
Location: src/transpiler_pro/core/repair.py
Description: The NLP-driven Linguistic Repair Engine.

This module uses spaCy to perform context-aware grammar corrections. Its primary 
responsibility is "Tense Shifting"—converting future tense ("will") into the 
present tense, as required by the SUSE Style Guide, while ensuring correct 
subject-verb agreement (e.g., "I will check" -> "I check" vs "It will check" -> "It checks").
"""

import spacy
import re
from spacy.util import filter_spans

# Ensure the spaCy NLP model is available; download it if necessary.
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class LinguisticEngine:
    """
    Handles advanced text repair using Natural Language Processing.
    
    Attributes:
        kb (dict): Branding and automated fix rules from the knowledge base.
    """

    def __init__(self, knowledge_base: dict):
        """Initializes the engine with branding rules."""
        self.kb = knowledge_base.get("automated_fixes", {})

    def repair_text(self, text: str) -> str:
        """
        Applies a multi-pass repair strategy to the provided text.

        1. Code Shielding: Protects [source] blocks from being linguistically altered.
        2. Aggressive Branding: Enforces SUSE, Wi-Fi, and IP casing rules.
        3. NLP Tense Shift: Converts future tense to present tense with subject awareness.
        4. Surgical Offsets: Replaces text using character indices to prevent regex collisions.
        """
        
        # --- PHASE 1: CODE SHIELDING ---
        # We replace code blocks with temporary placeholders so the NLP doesn't
        # try to "fix" variable names or terminal commands.
        protected_blocks = []
        def shield_code(match):
            placeholder = f"REPAIR_SHIELD_{len(protected_blocks)}_"
            protected_blocks.append(match.group(0))
            return placeholder

        text = re.sub(r'(\[source,.*?\]\n----\n(.*?)\n----)', shield_code, text, flags=re.DOTALL)

        # --- PHASE 2: AGGRESSIVE BRANDING ---
        # Replaces branding errors (e.g., 'suse' -> 'SUSE') globally.
        # Uses negative lookarounds to avoid breaking URLs or file paths.
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            # Guard against invalid or empty replacements that might corrupt the file.
            if not replacement or str(replacement).lower() in ["spellings", "spelling", "learned", "none", "val"]:
                continue
            
            # Pattern ensures we only match whole words, not parts of a path/URL.
            pattern = rf"(?i)(?<![a-zA-Z0-9/]){re.escape(key)}(?![a-zA-Z0-9])"
            text = re.sub(pattern, replacement, text)

        # --- PHASE 3: NLP ANALYSIS ---
        doc = nlp(text)
        
        # --- PHASE 4: HYPHEN MERGER ---
        # spaCy splits "re-prompt" into ["re", "-", "prompt"]. 
        # We merge them so the engine sees one verb instead of three tokens.
        # filter_spans ensures we don't crash on overlapping spans (like dates: 2026-03-25).
        spans_to_merge = []
        for token in doc:
            if token.text == "-" and token.i > 0 and token.i < len(doc) - 1:
                spans_to_merge.append(doc[token.i - 1 : token.i + 2])
                
        with doc.retokenize() as retokenizer:
            for span in filter_spans(spans_to_merge):
                retokenizer.merge(span)
        
        # Edits list stores (start_char, end_char, replacement_text)
        edits = []
        
        for token in doc:
            # Skip verbs already in the perfect tense (e.g., "I have checked").
            if token.pos_ == "VERB":
                auxiliaries = [w.lemma_.lower() for w in token.lefts if w.dep_ in ["aux", "auxpass"]]
                if "have" in auxiliaries:
                    continue

            # --- PHASE 5: THE TENSE SHIFTER (The "Final Boss") ---
            # Identifies "will" and determines how to conjugate the following verb.
            if token.pos_ == "AUX" and token.lemma_ == "will":
                
                # Check for "will be" (Passive/Progressive) vs "will [verb]" (Active)
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                is_passive_or_progressive = next_token and next_token.lemma_ == "be"
                
                # SUBJECT DETECTION: Scan backward for the nearest Noun/Pronoun.
                # This is more robust than dependency trees for complex or broken sentences.
                subject_token = None
                for j in range(token.i - 1, -1, -1):
                    if doc[j].pos_ in ["PRON", "NOUN", "PROPN"]:
                        subject_token = doc[j]
                        break
                
                # PLURALITY LOGIC: Decide if we need a singular or plural verb form.
                is_plural = False
                if subject_token:
                    t = subject_token.text.lower()
                    # "You", "We", "I", "They" always use the plural (base) form.
                    if t in ["you", "we", "i", "they"]:
                        is_plural = True
                    # Check for explicit plural tags from the NLP model.
                    elif subject_token.tag_ in ["NNS", "NNPS"] or "Number=Plur" in str(subject_token.morph):
                        is_plural = True
                    # Failsafe: Standard nouns ending in 's' (excluding specific exceptions).
                    elif t.endswith('s') and t not in ["status", "process", "this", "us", "analysis", "address", "class"]:
                        is_plural = True

                # SCENARIO A: "will be" -> "is/are"
                if is_passive_or_progressive:
                    replacement = "are" if is_plural else "is"
                    start_idx = token.idx
                    end_idx = next_token.idx + len(next_token.text)
                    edits.append((start_idx, end_idx, replacement))

                # SCENARIO B: "will [verb]" -> "[verb]s"
                else:
                    head = token.head
                    # Conjugate the "Head" verb attached to "will".
                    if head.pos_ in ["VERB", "AUX", "NOUN", "ADJ"] and head != token:
                        if "-" in head.text:
                            # Hyphenated verbs (re-prompt) get a simple 's' if singular.
                            replacement = head.text if is_plural else f"{head.text}s"
                        elif is_plural:
                            replacement = head.text # Plural/User: "check"
                        else:
                            replacement = self._conjugate_to_present(head) # Singular: "checks"
                            
                        # Remove "will" and its following space.
                        w_len = len(token.text) + len(token.whitespace_)
                        edits.append((token.idx, token.idx + w_len, ""))
                        # Replace the verb with its new conjugated form.
                        edits.append((head.idx, head.idx + len(head.text), replacement))

        # --- PHASE 6: SURGICAL REPLACEMENT ---
        # To prevent index shifting (where replacing word A moves word B), 
        # we apply all edits in REVERSE order from the end of the file.
        edits = sorted(list(set(edits)), key=lambda x: x[0], reverse=True)
        for start, end, rep in edits:
            text = text[:start] + rep + text[end:]

        # Restore code blocks.
        for i, original_content in enumerate(protected_blocks):
            text = text.replace(f"REPAIR_SHIELD_{i}_", original_content)

        return text

    def _conjugate_to_present(self, verb_token) -> str:
        """
        Helper: Conjugates a base verb to the 3rd-person singular present.
        
        Example: 
            "check" -> "checks"
            "fix"   -> "fixes"
            "study" -> "studies"
            "execute" -> "executes"
        """
        text = verb_token.text
        # Standard 'es' for sibilant sounds.
        if text.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return text + "es"
        # The 'y' to 'ies' rule.
        elif text.endswith('y') and len(text) > 1 and text[-2] not in "aeiou":
            return text[:-1] + "ies"
        # Standard 's' for everything else.
        else:
            return text + "s"