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
        2. Structural Preservation: Processes line-by-line to protect lists and headings.
        3. Aggressive Branding: Enforces SUSE, Wi-Fi, and IP casing rules.
        4. NLP Tense Shift: Converts future tense to present tense with subject awareness.
        5. Surgical Offsets: Replaces text using character indices to prevent regex collisions.
        """
        # --- PHASE 1: CODE SHIELDING ---
        protected_blocks = []
        def shield_code(match):
            placeholder = f" REPAIR_SHIELD_{len(protected_blocks)}_ "
            protected_blocks.append(match.group(0))
            return placeholder

        text = re.sub(r'(\[source,.*?\]\n----\n(.*?)\n----)', shield_code, text, flags=re.DOTALL)

        # --- PRE-PROCESS: FORCE NEWLINES ON SQUASHED LISTS ---
        # This fixes the issue where "* Pointer" is on the same line as prose.
        # It looks for a character followed by a space and a bullet marker.
        text = re.sub(r'([a-zA-Z0-9.])\s+([*.-]\s+)', r'\1\n\2', text)

        # --- PHASE 2: LINE-BY-LINE PROCESSING ---
        lines = text.splitlines()
        repaired_lines = []
        in_list_block = False # True if we are currently inside a sequence of bullets

        for line in lines:
            stripped = line.strip()
            
            # 1. Handle Empty Lines: Reset the list block state
            if not stripped:
                repaired_lines.append("")
                in_list_block = False
                continue
                
            # 2. Handle Structural Headers/Markers: Just append
            if line.startswith(('= ', '[#', ':', 'image::', 'xref:', '----', '[source')):
                repaired_lines.append(line)
                in_list_block = False
                continue
            
            # 3. Detect List Items (*, ., -)
            is_list = re.match(r'^[\s]*[*.-]+\s+', line)
            
            if is_list:
                # If we are starting a list but were NOT just in one, force a gap
                # This separates the list from the paragraph above it.
                if not in_list_block and repaired_lines and repaired_lines[-1] != "":
                    repaired_lines.append("") 
                
                marker_match = re.match(r'^([\s]*[*.-]+\s+)(.*)', line)
                marker, prose = marker_match.group(1), marker_match.group(2)
                repaired_lines.append(marker + self._process_prose_nlp(prose))
                
                # Mark that we are now inside a list block (next bullet shouldn't trigger a gap)
                in_list_block = True
            
            # 4. Handle Standard Prose
            else:
                repaired_lines.append(self._process_prose_nlp(line))
                in_list_block = False # We are in a paragraph, not a list block

        final_text = "\n".join(repaired_lines)

        # --- PHASE 7: RESTORE CODE BLOCKS ---
        for i, original_content in enumerate(protected_blocks):
            final_text = final_text.replace(f" REPAIR_SHIELD_{i}_ ", original_content)

        return final_text

    def _process_prose_nlp(self, text: str) -> str:
        """
        Helper method that contains your original NLP and Branding logic.
        This is now applied only to individual lines of prose.
        """
        # --- PHASE 3: AGGRESSIVE BRANDING ---
        # Replaces branding errors (e.g., 'suse' -> 'SUSE') globally.
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            if not replacement or str(replacement).lower() in ["spellings", "spelling", "learned", "none", "val"]:
                continue
            
            # Pattern ensures we only match whole words, fixing the 'bes' bug inside 'describes'
            pattern = rf"(?i)\b{re.escape(key)}\b"
            text = re.sub(pattern, str(replacement), text)

        # --- PHASE 4: NLP ANALYSIS ---
        doc = nlp(text)
        
        # --- PHASE 5: HYPHEN MERGER ---
        spans_to_merge = []
        for token in doc:
            if token.text == "-" and token.i > 0 and token.i < len(doc) - 1:
                spans_to_merge.append(doc[token.i - 1 : token.i + 2])
                
        with doc.retokenize() as retokenizer:
            for span in filter_spans(spans_to_merge):
                retokenizer.merge(span)
        
        edits = []
        
        for token in doc:
            # Skip verbs already in the perfect tense
            if token.pos_ == "VERB":
                auxiliaries = [w.lemma_.lower() for w in token.lefts if w.dep_ in ["aux", "auxpass"]]
                if "have" in auxiliaries:
                    continue

            # --- PHASE 6: THE TENSE SHIFTER ---
            if token.pos_ == "AUX" and token.lemma_ == "will":
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                is_passive_or_progressive = next_token and next_token.lemma_ == "be"
                
                subject_token = None
                for j in range(token.i - 1, -1, -1):
                    if doc[j].pos_ in ["PRON", "NOUN", "PROPN"]:
                        subject_token = doc[j]
                        break
                
                is_plural = False
                if subject_token:
                    # Look for the 'Head' of the subject phrase. 
                    # In "The set of instructions", the head of 'instructions' is 'set'.
                    actual_subject = subject_token
                    if subject_token.dep_ == "pobj" and subject_token.head.dep_ == "prep":
                         actual_subject = subject_token.head.head

                    t = actual_subject.text.lower()
                    
                    # 1. Check for specific plural pronouns
                    if t in ["you", "we", "i", "they"]:
                        is_plural = True
                    # 2. Trust the Morphological Number (Singular vs Plural)
                    elif "Number=Plur" in str(actual_subject.morph):
                        is_plural = True
                    # 3. Standard NLP tags as failsafe
                    elif actual_subject.tag_ in ["NNS", "NNPS"]:
                        is_plural = True

                if is_passive_or_progressive:
                    replacement = "are" if is_plural else "is"
                    start_idx = token.idx
                    end_idx = next_token.idx + len(next_token.text)
                    edits.append((start_idx, end_idx, replacement))
                else:
                    head = token.head
                    if head.pos_ in ["VERB", "AUX", "NOUN", "ADJ"] and head != token:
                        if "-" in head.text:
                            replacement = head.text if is_plural else f"{head.text}s"
                        elif is_plural:
                            replacement = head.text
                        else:
                            replacement = self._conjugate_to_present(head)
                            
                        w_len = len(token.text) + len(token.whitespace_)
                        edits.append((token.idx, token.idx + w_len, ""))
                        edits.append((head.idx, head.idx + len(head.text), replacement))

        # --- PHASE 6: SURGICAL OFFSETS ---
        # We sort edits in reverse order to avoid messing up indices as we replace text.
        edits = sorted(list(set(edits)), key=lambda x: x[0], reverse=True)
        for start, end, rep in edits:
            text = text[:start] + rep + text[end:]

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