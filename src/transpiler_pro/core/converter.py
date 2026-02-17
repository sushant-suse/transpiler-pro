"""Location: src/transpiler_pro/core/converter.py
Description: Data-driven DocConverter. Optimized restoration logic to prevent
marker artifacts and text swallowing.
"""

import re
import subprocess
import tomllib
from pathlib import Path
from typing import Match, Optional, Dict, Any

class DocConverter:
    """A generic transformation engine driven by configuration patterns."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_project_config()
        self.conv_cfg = self.config.get("conversions", {})

    def _load_project_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}

    def pre_process_markdown(self, content: str) -> str:
        """Shields blocks using patterns defined entirely in configuration."""
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
        """Restores markers and cleans artifacts based on strict TOML rules."""
        # 1. Generic Cleanup
        cleanup = self.conv_cfg.get("cleanup_regex", [])
        for c in cleanup:
            flags = re.M if c.get("flags") == "M" else 0
            content = re.sub(c["regex"], c["replacement"], content, flags=flags)

        # 2. Dynamic Marker Restoration (Improved regex handling)
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
                        # We use \s* inside the regex to be forgiving of kramdoc's spacing
                        current_regex = regex.replace("{key}", key)
                        current_replace = replacement.replace("{val}", val)
                        content = re.sub(current_regex, current_replace, content, flags=re.S)
                else:
                    content = re.sub(regex, replacement, content, flags=re.S)

        # 3. Dynamic XREFs (Zero-Hardcoded)
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
        raw_md = input_path.read_text(encoding='utf-8')
        ready_md = self.pre_process_markdown(raw_md)
        
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md)
        
        try:
            subprocess.run(
                ["kramdoc", "--wrap", "ventilate", "-o", str(output_path), str(temp_md)], 
                check=True, capture_output=True
            )
            
            final_adoc = self.post_process_asciidoc(output_path.read_text())
            output_path.write_text(final_adoc)
        finally:
            if temp_md.exists(): 
                temp_md.unlink()