"""
Location: src/transpiler_pro/core/converter.py

Description: Core Transformation Engine for Transpiler-Pro.

This module provides the `DocConverter` class, which handles the structural 
transformation of Markdown into AsciiDoc using a three-phase pipeline:

1. **Shielding**: Protecting complex Markdown (like admonitions) with markers.
2. **Transpilation**: Utilizing Pandoc for base format conversion.
3. **Restoration**: Converting markers back into native AsciiDoc syntax.
"""

import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Match, Optional, Dict, Any

class DocConverter:
    """
    A data-driven transformation engine driven by configuration patterns.
    
    Attributes:
        config_path (Path): Path to the TOML configuration file.
        config (Dict): The loaded configuration for the transpiler.
        conv_cfg (Dict): Conversion-specific patterns and rules.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initializes the converter with settings from the provided config path."""
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_project_config()
        self.conv_cfg = self.config.get("conversions", {})
        self.metadata = {"title": "", "description": ""}

    def _load_project_config(self) -> Dict[str, Any]:
        """Loads the configuration block from the TOML file."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}

    def pre_process_markdown(self, content: str) -> str:
        """
        Shields Markdown blocks and extracts metadata for the header.
        
        Args:
            content: Raw Markdown string.
            
        Returns:
            Markdown string with complex blocks replaced by markers.
        """
        # Extract metadata from frontmatter before it's gone
        title_match = re.search(r"(?m)^title:\s*(.*)", content)
        desc_match = re.search(r"(?m)^description:\s*(.*)", content)
        
        if title_match:
            self.metadata["title"] = title_match.group(1).strip()
        if desc_match:
            self.metadata["description"] = desc_match.group(1).strip()

        patterns = self.conv_cfg.get("shielding_patterns", [])
        
        for p in patterns:
            regex = p.get("regex")
            replacement = p.get("replacement")
            
            if p.get("hook") == "protect_spaces":
                def protect_hook(match: Match) -> str:
                    # Replaces spaces in titles to prevent Pandoc from breaking the marker
                    title = match.group(1).strip().replace(' ', 'PROTECTSPACE')
                    body = match.group(2).strip()
                    return replacement.replace(r"\1", title).replace(r"\2", body)
                content = re.sub(regex, protect_hook, content, flags=re.S)
            else:
                content = re.sub(regex, replacement, content, flags=re.S)
        
        return content

    def post_process_asciidoc(self, content: str) -> str:
        """
        Restores markers and cleans artifacts based on strict TOML rules.
        
        Args:
            content: Raw AsciiDoc produced by the transpiler.
            
        Returns:
            Finalized AsciiDoc with native syntax restored.
        """
        from datetime import datetime

        # 1. Generic Cleanup (e.g., removing frontmatter artifacts)
        cleanup = self.conv_cfg.get("cleanup_regex", [])
        for c in cleanup:
            flags = re.M if c.get("flags") == "M" else 0
            regex = c.get("regex")
            replacement = c.get("replacement")
            
            if c.get("hook") == "uppercase_label":
                def uppercase_hook(match: Match) -> str:
                    # group(1) is the label (Note/Tip), group(2) is the content
                    label = match.group(1).upper() 
                    body = match.group(2).strip()
                    return f"[{label}]\n====\n{body}\n===="
                content = re.sub(regex, uppercase_hook, content, flags=flags)
            else:
                content = re.sub(regex, replacement, content, flags=flags)

        # 2. Dynamic Marker Restoration
        restorations = self.conv_cfg.get("restoration_patterns", [])
        for r in restorations:
            regex = r.get("regex")
            replacement = r.get("replacement")
            
            if r.get("hook") == "restore_spaces":
                def restore_hook(match: Match) -> str:
                    # Logic to handle the split between title and body in collapsibles
                    full_block = match.group(1)
                    if "SHIELDSEP" in full_block:
                        parts = full_block.split("SHIELDSEP", 1)
                    else:
                        parts = full_block.split("\n", 1)
                    
                    title = parts[0].replace('PROTECTSPACE', ' ').strip()
                    body = parts[1].strip() if len(parts) > 1 else ""
                    return f".{title}\n[%collapsible]\n======\n{body}\n======"
                content = re.sub(regex, restore_hook, content, flags=re.S)
            else:
                mapping = r.get("map")
                if mapping:
                    for key, val in mapping.items():
                        current_regex = regex.replace("{key}", key)
                        current_replace = replacement.replace("{val}", val)
                        content = re.sub(current_regex, current_replace, content, flags=re.S)
                else:
                    content = re.sub(regex, replacement, content, flags=re.S)

        # 3. Structural Polish (Heading-to-List Spacing)
        # Fixes missing space between "== Heading" and ". List Item" or "* Item"
        content = re.sub(r"(^={1,6} .*)\n([.*])", r"\1\n\n\2", content, flags=re.M)

        # 4. Dynamic XREFs and Extension Mapping
        ext_map = self.conv_cfg.get("extension_map", {})
        if ext_map:
            normalization = self.conv_cfg.get("path_normalization", [])
            
            def clean_xref(match: Match) -> str:
                path, ext = match.group(1), match.group(2)
                for rule in normalization:
                    path = re.sub(rule["regex"], rule["replacement"], path)
                
                new_ext = ext_map.get(ext, ext)
                return f'xref:{path}.{new_ext}'
            
            xref_pattern = self.conv_cfg.get("xref_detection_regex", r'link:((?!http)[^ ]*)\.(md|json|yaml|yml)')
            content = re.sub(xref_pattern, clean_xref, content)

        # 5. Final Header Construction & Section Promotion
        today = datetime.now().strftime("%Y-%m-%d")
        title = self.metadata.get("title") or "Untitled Document"
        description = self.metadata.get("description", "")
        
        # PROMOTE SECTIONS: Pandoc often strips '=' from secondary H1s (like Section 1/2).
        # We manually re-insert the Level 0 marker for any line starting with "Section X:".
        content = re.sub(r"^(Section \d+:.*)$", r"= \1", content, flags=re.M)
        
        # Build header block
        header_lines = [
            f"= {title}",
            f":description: {description}",
            f":revdate: {today}"
        ]
        
        antora_cfg = self.config.get("antora", {})
        header_lines.extend(antora_cfg.get("headers", []))
        
        header_block = "\n".join(header_lines) + "\n\n"
        
        # Remove Pandoc's generated Document Title line ONLY IF it matches our extracted title
        # This ensures we don't accidentally delete the newly promoted sections.
        content = re.sub(rf"^= {re.escape(title)}\n?", "", content, flags=re.M).strip()
        
        return header_block + content
    
    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """
        Orchestrates the conversion of a single file.
        """
        raw_md = input_path.read_text(encoding='utf-8')
        ready_md = self.pre_process_markdown(raw_md)
        
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md, encoding='utf-8')
        
        try:
            # PANDOC INTEGRATION
            # --shift-heading-level-by=-1 natively shifts H1 (#) to Level 0 (=)
            subprocess.run(
                [
                    "pandoc", 
                    "-f", "markdown", 
                    "-t", "asciidoc", 
                    "--shift-heading-level-by=-1",
                    "--wrap=none", 
                    "-o", str(output_path), 
                    str(temp_md)
                ], 
                check=True, 
                capture_output=True
            )
            
            final_adoc = self.post_process_asciidoc(output_path.read_text(encoding='utf-8'))
            output_path.write_text(final_adoc, encoding='utf-8')
        finally:
            if temp_md.exists(): 
                temp_md.unlink()