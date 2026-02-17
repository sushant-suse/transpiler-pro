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
        Shields Markdown blocks using patterns defined in configuration.
        
        Args:
            content: Raw Markdown string.
            
        Returns:
            Markdown string with complex blocks replaced by markers.
        """
        patterns = self.conv_cfg.get("shielding_patterns", [])
        
        for p in patterns:
            regex = p.get("regex")
            replacement = p.get("replacement")
            
            if p.get("hook") == "protect_spaces":
                def protect_hook(match: Match) -> str:
                    title = match.group(1).strip().replace(' ', 'PROTECT_SPACE')
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
        # 1. Generic Cleanup (e.g., removing frontmatter artifacts)
        cleanup = self.conv_cfg.get("cleanup_regex", [])
        for c in cleanup:
            flags = re.M if c.get("flags") == "M" else 0
            content = re.sub(c["regex"], c["replacement"], content, flags=flags)

        # 2. Dynamic Marker Restoration
        restorations = self.conv_cfg.get("restoration_patterns", [])
        for r in restorations:
            regex = r.get("regex")
            replacement = r.get("replacement")
            
            if r.get("hook") == "restore_spaces":
                def restore_hook(match: Match) -> str:
                    title = match.group(1).replace('PROTECT_SPACE', ' ').strip()
                    body = match.group(2).strip()
                    return replacement.replace(r"\1", title).replace(r"\2", body)
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

        # 3. Dynamic XREFs and Extension Mapping
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

        return content.strip()

    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """
        Orchestrates the conversion of a single file.
        
        Uses Pandoc for the base conversion from Markdown to AsciiDoc.
        """
        raw_md = input_path.read_text(encoding='utf-8')
        ready_md = self.pre_process_markdown(raw_md)
        
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md)
        
        try:
            # PANDOC INTEGRATION: Replaces kramdoc
            # --ascii is used to ensure high compatibility with Antora/AsciiDoc
            subprocess.run(
                [
                    "pandoc", 
                    "-f", "markdown", 
                    "-t", "asciidoc", 
                    "--wrap=none", 
                    "-o", str(output_path), 
                    str(temp_md)
                ], 
                check=True, 
                capture_output=True
            )
            
            final_adoc = self.post_process_asciidoc(output_path.read_text())
            output_path.write_text(final_adoc)
        finally:
            if temp_md.exists(): 
                temp_md.unlink()