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

        Args:
            text (str): The raw text to be repaired.
        
        Returns:
            str: The linguistically repaired text.
        """
        # --- 1. CODE SHIELDING ---
        protected_blocks = []

        def shield_code(match: re.Match) -> str:
            """
            Replaces code blocks with placeholders to protect them from NLP processing.

            Args:
                match (re.Match): A regex match object for a [source] block.
            
            Returns:
                str: A unique placeholder string that will be replaced back later.
            """
            placeholder = f" REPAIR_SHIELD_{len(protected_blocks)}_ "
            protected_blocks.append(match.group(0))
            return placeholder

        text = re.sub(r'(\[source,.*?\]\n----\n(.*?)\n----)', shield_code, text, flags=re.DOTALL)

        # --- 2. FORCE NEWLINES ON SQUASHED LISTS ---
        # Only split if the preceding character is end-of-sentence punctuation or a closing bracket
        text = re.sub(r'([.?!>\]])\s+([*.-]\s+)(?!\d{4})', r'\1\n\2', text)

        # --- 3. LINE-BY-LINE PROCESSING ---
        lines = text.splitlines()
        repaired_lines = []
        in_list_block = False # True if we are currently inside a sequence of bullets

        # We process the text line by line to preserve structural elements like lists and headings, 
        # while applying NLP repairs only to prose lines. The in_list_block flag helps us determine 
        # when we are inside a list, so we can ensure proper spacing between list items and prevent 
        # unintended merges of adjacent bullets.
        for line in lines:
            stripped = line.strip()
            
            # 1. Handle Empty Lines: Reset the list block state
            if not stripped:
                repaired_lines.append("")
                in_list_block = False
                continue
                
            # 2. Handle Structural Headers/Markers: Just append without NLP processing and reset list state.
            # This includes headings (e.g., "= Heading"), admonitions, images, xrefs, and horizontal rules.
            if line.startswith(('=', '[#', ':', 'image::', 'xref:', '----', '[source')):
                repaired_lines.append(line)
                in_list_block = False
                continue
            
            # 3. Detect List Items (*, ., -)
            is_list = re.match(r'^[\s]*[*.-]+\s+(?!\d{4}-\d{2}-\d{2})', line)
            
            if is_list:
                # If we are starting a list but were NOT just in one, force a gap
                if not in_list_block and repaired_lines and repaired_lines[-1] != "":
                    repaired_lines.append("") 
                
                # Process the prose part of the list item separately to preserve the bullet marker and spacing.
                marker_match = re.match(r'^([\s]*[*.-]+\s+)(.*)', line)
                marker, prose = marker_match.group(1), marker_match.group(2)
                repaired_lines.append(marker + self._process_prose_nlp(prose))
                
                in_list_block = True
            
            # 4. Handle Standard Prose
            else:
                repaired_lines.append(self._process_prose_nlp(line))
                in_list_block = False

        final_text = "\n".join(repaired_lines)

        # --- 4. RESTORE CODE BLOCKS ---
        for i, original_content in enumerate(protected_blocks):
            final_text = final_text.replace(f" REPAIR_SHIELD_{i}_ ", original_content)

        # --- 5. UNCLOAK THE HYPHENS ---
        final_text = final_text.replace("&#45;", "-")

        # --- 6. SANITY CHECK (The "Anti-Hallucination" Filter) ---
        # Normalize spaces to destroy Pandoc's invisible U+00A0
        final_text = final_text.replace('\u00a0', ' ')

        # Catch NLP Tense Shifting hallucinations
        final_text = final_text.replace(" haves ", " have ")
        final_text = final_text.replace(" bes able", " is able")
        final_text = final_text.replace(" no longer bes ", " no longer is ")
        final_text = final_text.replace(" certain other ", " some other ")

        return final_text
    

    def _process_prose_nlp(self, text: str) -> str:
        """
        Helper method that contains your original NLP and Branding logic.
        This is now applied only to individual lines of prose.

        Args:
            text (str): A single line of text to process with NLP and branding rules.
        
        Returns:
            str: The processed line of text after applying branding and NLP repairs.
        """
        # --- 1. AGGRESSIVE BRANDING ---
        sorted_keys = sorted(self.kb.keys(), key=len, reverse=True)
        for key in sorted_keys:
            replacement = self.kb[key]
            
            # [GLOBAL GUARDRAIL] 
            # We strictly enforce 1-to-1 replacements (e.g., 'suse' -> 'SUSE').
            # If a rule tries to blindly delete a word (empty string), we safely ignore it.
            if not replacement or not any(char.isalnum() for char in str(replacement)):
                continue
            
            pattern = rf"(?i)\b{re.escape(key)}\b"
            text = re.sub(pattern, str(replacement), text)

        # --- 2. NLP ANALYSIS ---
        doc = nlp(text)
        
        # --- 3. HYPHEN MERGER ---
        spans_to_merge = []
        for token in doc:
            if token.text == "-" and token.i > 0 and token.i < len(doc) - 1:
                spans_to_merge.append(doc[token.i - 1 : token.i + 2])
                
        with doc.retokenize() as retokenizer:
            for span in filter_spans(spans_to_merge):
                retokenizer.merge(span)
        
        edits = []
        
        # --- 4. THE FUTURE TENSE DETECTOR & SHIFTER ---
        for token in doc:
            if token.pos_ == "VERB":
                auxiliaries = [w.lemma_.lower() for w in token.lefts if w.dep_ in ["aux", "auxpass"]]
                if "have" in auxiliaries:
                    continue

            # --- 5. THE TENSE SHIFTER ---
            # We look for auxiliary verbs that indicate future tense (e.g., "will") and then determine 
            # if they are part of a passive or progressive construction. We also identify the subject 
            # to ensure correct agreement when shifting to present tense. The edits are collected as 
            # character offsets to be applied later, ensuring that we don't interfere with the tokenization process while iterating.
            if token.pos_ == "AUX" and token.lemma_ == "will":
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                is_passive_or_progressive = next_token and next_token.lemma_ == "be"
                
                subject_token = None
                for j in range(token.i - 1, -1, -1):
                    if doc[j].pos_ in ["PRON", "NOUN", "PROPN"]:
                        subject_token = doc[j]
                        break
                
                is_plural = False

                # We determine if the subject is plural based on pronoun forms, morphological features, or POS tags.
                if subject_token:
                    actual_subject = subject_token
                    if subject_token.dep_ == "pobj" and subject_token.head.dep_ == "prep":
                         actual_subject = subject_token.head.head

                    t = actual_subject.text.lower()
                    
                    if t in ["you", "we", "i", "they"]:
                        is_plural = True
                    elif "Number=Plur" in str(actual_subject.morph):
                        is_plural = True
                    elif actual_subject.tag_ in ["NNS", "NNPS"]:
                        is_plural = True

                # Based on the analysis, we determine the appropriate replacement for "will". 
                # If it's part of a passive or progressive construction, we replace "will" with "is/are" depending on plurality. 
                # Otherwise, we conjugate the main verb to present tense and remove "will". The edits are stored as 
                # character offsets to be applied after the loop to avoid modifying the token stream while iterating.
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
                            
                        # If it's a contraction like "'ll", don't swallow the trailing space
                        if token.text.startswith("'"):
                            edits.append((token.idx, token.idx + len(token.text), ""))
                        else:
                            w_len = len(token.text) + len(token.whitespace_)
                            edits.append((token.idx, token.idx + w_len, ""))
                        edits.append((head.idx, head.idx + len(head.text), replacement))

        # --- 6. SURGICAL OFFSETS ---
        edits = sorted(list(set(edits)), key=lambda x: x[0], reverse=True)
        for start, end, rep in edits:
            text = text[:start] + rep + text[end:]

        return text
    

    def _conjugate_to_present(self, verb_token) -> str:
        """
        Conjugates a verb token to present tense, handling subject-verb agreement for third-person singular.

        Args:
            verb_token (spacy.tokens.Token): The verb token to conjugate.
        
        Returns:
            str: The conjugated verb in present tense.
        """
        text = verb_token.text
        if text.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return text + "es"
        elif text.endswith('y') and len(text) > 1 and text[-2] not in "aeiou":
            return text[:-1] + "ies"
        else:
            return text + "s"
        