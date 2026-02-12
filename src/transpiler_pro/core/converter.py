"""Location: src/transpiler_pro/core/converter.py
Description: The core transformation engine for Personal Transpiler-Pro. 
Handles pre-processing, kramdoc integration, and post-processing to ensure 
high-fidelity conversion from Markdown to Antora-compliant AsciiDoc.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, Match


class DocConverter:
    """A deterministic conversion engine that transforms Markdown into AsciiDoc.
    
    The engine uses a 'Marker Strategy' to shield specific Markdown components 
    (like admonitions and collapsible blocks) that are typically mishandled by 
    standard conversion tools.
    """

    def __init__(self):
        # Map of Markdown-style admonition types to AsciiDoc-standard types
        self.ad_map: Dict[str, str] = {
            'note': 'NOTE', 
            'info': 'IMPORTANT', 
            'tip': 'TIP', 
            'warning': 'CAUTION'
        }

    def pre_process_markdown(self, content: str) -> str:
        """Shields complex Markdown elements before the primary transpilation phase.
        
        Args:
            content (str): The raw Markdown input.
            
        Returns:
            str: Markdown content with complex blocks replaced by stable markers.
        """
        # 1. Protect Admonitions (:::type ... :::)
        # We wrap these in unique markers to prevent line-merging during transpilation
        ad_pattern = r':::(?P<type>\w+)\n(?P<body>.*?)\n:::'
        content = re.sub(
            ad_pattern, 
            r'MARKER_ADMON_START_\1\n\2\nMARKER_ADMON_END', 
            content, 
            flags=re.S
        )
        
        # 2. Protect Collapsible Details (<details><summary>...</summary>...</details>)
        # We glue the summary text using 'PROTECT_SPACE' to prevent kramdoc from wrapping titles
        def protect_summary(match: Match) -> str:
            title = match.group('title').strip().replace(' ', 'PROTECT_SPACE')
            body = match.group('body').strip()
            return f"MARKER_COLL_START_{title}\n{body}\nMARKER_COLL_END"

        coll_pattern = r'<details>\s*<summary>(?P<title>.*?)</summary>\s*(?P<body>.*?)\s*</details>'
        content = re.sub(coll_pattern, protect_summary, content, flags=re.S)
        
        return content

    def post_process_asciidoc(self, content: str) -> str:
        """Finalizes the AsciiDoc structure by restoring markers and refining syntax.
        
        Args:
            content (str): The raw AsciiDoc output from kramdoc.
            
        Returns:
            str: Polished, Antora-compliant AsciiDoc content.
        """
        # 1. Clean up Metadata: Remove kramdoc-specific headers and auto-generated IDs
        content = re.sub(r'^:.*?\n', '', content, flags=re.M)
        content = re.sub(r'\[#.*?\]\n', '', content)
        
        # 2. Restore Admonitions: Reconstruct markers into standard [TYPE] blocks
        for md_type, ad_type in self.ad_map.items():
            pattern = rf'MARKER_ADMON_START_{md_type}\s*(.*?)\s*MARKER_ADMON_END'
            content = re.sub(pattern, rf'[{ad_type}]\n====\n\1\n====', content, flags=re.S)

        # 3. Handle Legacy Notes: Convert blockquote notes (e.g., '> Note:') into formal blocks
        content = re.sub(r'____\n\*Note\*:\s*(.*?)\n____', r'[NOTE]\n====\n\1\n====', content, flags=re.S)
        content = re.sub(r'^NOTE:\s*(.*)$', r'[NOTE]\n====\n\1\n====', content, flags=re.M)

        # 4. Refine Navigation: Convert internal links into Antora XREFs
        def clean_xref(match: Match) -> str:
            path = match.group(1)
            ext = match.group(2)
            # Normalize path: remove redundant './' prefixes
            path = re.sub(r'^\.\/', '', path)
            # Map .md extensions to .adoc
            new_ext = 'adoc' if ext == 'md' else ext
            return f'xref:{path}.{new_ext}'

        # Match relative links while ignoring absolute 'http' URLs
        content = re.sub(r'link:((?!http)[^ ]*)\.(md|json|yaml|yml)', clean_xref, content)

        # 5. Correct List Depth: Fix nested numbering level in mixed bullet/number lists
        content = re.sub(r'(\* .*?\n)\. ', r'\1.. ', content)

        # 6. Admonition Safety: Convert internal headers to bold to avoid syntax collision
        def fix_internal_headings(match: Match) -> str:
            header, body = match.group(1), match.group(2)
            fixed_body = re.sub(r'^={1,6}\s+(.*)$', r'*\1*', body, flags=re.M)
            return f"{header}\n====\n{fixed_body}\n===="
        content = re.sub(r'(\[(?:IMPORTANT|NOTE|TIP|CAUTION)\])\n====\n(.*?)\n====', fix_internal_headings, content, flags=re.S)

        # 7. Restore Collapsible Blocks: Rebuild [%collapsible] sections
        pattern_coll = r'MARKER_COLL_START_(.*?)\s+(.*?)\s*MARKER_COLL_END'
        def restore_collapsible(match: Match) -> str:
            title = match.group(1).replace('PROTECT_SPACE', ' ').strip()
            body = match.group(2).strip()
            return f".{title}\n[%collapsible]\n======\n{body}\n======"
        content = re.sub(pattern_coll, restore_collapsible, content, flags=re.S)

        # 8. Structural Cleanup: Remove excess whitespace for clean output
        content = re.sub(r'(\[.*?\])\n\n+(====|======)', r'\1\n\2', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()

    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """Executes the full conversion pipeline for a single file.

        Args:
            input_path (Path): The path to the source Markdown file.
            output_path (Path): The path where the converted AsciiDoc will be saved.
            
        Raises:
            subprocess.CalledProcessError: If the underlying kramdoc execution fails.
            IOError: If there are issues reading or writing the files.
        """
        # Load raw content
        raw_md = input_path.read_text(encoding='utf-8')
        
        # Phase 1: Pre-process
        ready_md = self.pre_process_markdown(raw_md)
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md)

        try:
            # Phase 2: Core Transpilation
            # We use '--wrap ventilate' to maintain logical line breaks for better regex matching
            subprocess.run([
                "kramdoc", "--wrap", "ventilate", "--auto-ids",
                "-o", str(output_path), str(temp_md)
            ], check=True)
            
            # Phase 3: Post-process and cleanup
            adoc_output = output_path.read_text()
            final_adoc = self.post_process_asciidoc(adoc_output)
            output_path.write_text(final_adoc)
            
        finally:
            # Always remove the temporary shielded file
            if temp_md.exists():
                temp_md.unlink()
