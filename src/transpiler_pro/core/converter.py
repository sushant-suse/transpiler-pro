"""
Location: src/transpiler_pro/core/converter.py

Description: Core Transformation Engine for Transpiler-Pro.
Final Version: Integrated Title Scavenging, Video Integrity, and List Spacing.
"""

import re
import subprocess
import yaml
from datetime import datetime
from pathlib import Path
from typing import Match, Optional, Dict, Any

class DocConverter:
    """
    A data-driven transformation engine driven by configuration patterns.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initializes the converter with settings from the provided config path."""
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_project_config()
        self.conv_cfg = self.config.get("conversions", {})
        # Dynamic metadata storage to capture ALL frontmatter keys
        self.metadata: Dict[str, Any] = {}
        self.discovered_title: Optional[str] = None

    def _load_project_config(self) -> Dict[str, Any]:
        """Loads the configuration block from the TOML file."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                import tomllib
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}

    def pre_process_markdown(self, content: str) -> str:
        """
        Shields Markdown blocks and extracts metadata for the header.
        """
        # --- 1. SOPHISTICATED FRONTMATTER EXTRACTION ---
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        
        if frontmatter_match:
            try:
                yaml_data = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(yaml_data, dict):
                    self.metadata = yaml_data
                content = content[frontmatter_match.end():]
            except Exception:
                self.metadata = {}

        # --- 2. TITLE SCAVENGER (CRITICAL FIX) ---
        # Capture the H1 while it's still Markdown (#) to prevent "H2 Hijacking"
        self.discovered_title = self.metadata.get('title')
        if not self.discovered_title:
            h1_match = re.search(r'^#\s+(.*)$', content, re.M)
            if h1_match:
                self.discovered_title = h1_match.group(1).strip()
                # Remove from body so it's not duplicated below the header
                content = content.replace(h1_match.group(0), "", 1)

        # --- 3. VIDEO IFRAME SHIELDING ---
        # Use alphanumeric tokens to prevent Pandoc from injecting '++' passthroughs
        content = re.sub(r'<iframe.*?embed/([^"?\s]+).*?</iframe>', r'VIDEOTOKEN\1', content)

        patterns = self.conv_cfg.get("shielding_patterns", [])
        for p in patterns:
            regex = p.get("regex")
            replacement = p.get("replacement")
            
            if p.get("hook") == "protect_spaces":
                def protect_hook(match: Match) -> str:
                    title = match.group(1).strip().replace(' ', 'PROTECTSPACE')
                    body = match.group(2).strip()
                    return replacement.replace(r"\1", title).replace(r"\2", body)
                content = re.sub(regex, protect_hook, content, flags=re.S)
            else:
                content = re.sub(regex, replacement, content, flags=re.S)
        
        return content

    def post_process_asciidoc(self, content: str) -> str:
        """
        Restores markers and constructs the finalized AsciiDoc header.
        """
        # --- 1. MARKER RESTORATION (VIDEO & CLEANUP) ---
        content = re.sub(r'VIDEOTOKEN([a-zA-Z0-9_-]+)', r'video::\1[youtube]', content)
        
        # ASCII De-smarting
        content = content.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('…', '...')

        cleanup = self.conv_cfg.get("cleanup_regex", [])
        for c in cleanup:
            flags = re.M if c.get("flags") == "M" else 0
            regex = c.get("regex")
            replacement = c.get("replacement")
            
            if c.get("hook") == "uppercase_label":
                def uppercase_hook(match: Match) -> str:
                    label = match.group(1).upper() 
                    body = match.group(2).strip()
                    return f"[{label}]\n====\n{body}\n===="
                content = re.sub(regex, uppercase_hook, content, flags=flags)
            else:
                content = re.sub(regex, replacement, content, flags=flags)

        # --- 2. ADMONITION PROMOTION (Aggressive Case-Insensitive) ---
        def promote_admo(match: Match) -> str:
            label = match.group(1).upper()
            body = match.group(2).strip()
            return f"[{label}]\n====\n{body}\n===="
        
        content = re.sub(r'(?i)^\*?(Note|Warning|Tip|Caution|Important|IMPORTANT)[:]?\*?\s+(.*)$', promote_admo, content, flags=re.M)

        # --- 3. DYNAMIC MARKER RESTORATION ---
        restorations = self.conv_cfg.get("restoration_patterns", [])
        for r in restorations:
            regex, replacement = r.get("regex"), r.get("replacement")
            if r.get("hook") == "restore_spaces":
                def restore_hook(match: Match) -> str:
                    full_block = match.group(1)
                    parts = full_block.split("SHIELDSEP", 1) if "SHIELDSEP" in full_block else full_block.split("\n", 1)
                    title = parts[0].replace('PROTECTSPACE', ' ').strip()
                    body = parts[1].strip() if len(parts) > 1 else ""
                    return f".{title}\n[%collapsible]\n======\n{body}\n======"
                content = re.sub(regex, restore_hook, content, flags=re.S)
            else:
                mapping = r.get("map")
                if mapping:
                    for key, val in mapping.items():
                        content = re.sub(regex.replace("{key}", key), replacement.replace("{val}", val), content, flags=re.S)
                else:
                    content = re.sub(regex, replacement, content, flags=re.S)

        # --- 4. LIST STITCHING (FIXES SQUASHED/DETACHED LISTS) ---
        # Remove excess newlines between parent (*) and child (**) items
        content = re.sub(r'(\n\s*\*.*)\n+(\s*\*\*)', r'\1\n\2', content)

        # --- 5. ANTORA XREFS & IMAGE PATHS ---
        content = re.sub(r'image::/images/(.*?)\[', r'image::\1[', content)
        
        def antora_xref_logic(match: Match) -> str:
            raw_path, anchor = match.group(1), match.group(2)
            path = raw_path.strip("/") if raw_path else ""
            if path and not path.endswith(".adoc"):
                path = f"{path}.adoc"
            cl_anchor = ""
            if anchor:
                cl_anchor = "#_" + anchor.replace("#", "").lower().replace("-", "_")
            return f"xref:{path}{cl_anchor}"

        # Handles standard link: and removes residual ++ passthroughs
        content = re.sub(r'link:(?:\+\+)?(/[^\[\s#\+]+)?(#[^\[\s\+]+)?(?:\+\+)?', antora_xref_logic, content)

        # --- 6. FINAL HEADER CONSTRUCTION ---
        today = datetime.now().strftime("%Y-%m-%d")
        header_lines = [f"= {self.discovered_title or 'Untitled Document'}"]
        
        for key, value in self.metadata.items():
            if key.lower() != "title": # Discovered title is already in L0 position
                header_lines.append(f":{key}: {value}")
        
        header_lines.append(f":revdate: {today}")
        
        antora_cfg = self.config.get("antora", {})
        header_lines.extend(antora_cfg.get("headers", []))
        
        header_block = "\n".join(header_lines) + "\n\n"
        
        # Section Promotion (Cleanup)
        content = re.sub(r"^(Section \d+:.*)$", r"= \1", content, flags=re.M)
        content = content.replace("PROTECTSPACE", " ").replace("SHIELDSEP", "\n")
        
        return header_block + content.strip()
    
    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """Orchestrates the conversion of a single file."""
        raw_md = input_path.read_text(encoding='utf-8')
        ready_md = self.pre_process_markdown(raw_md)
        
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md, encoding='utf-8')
        
        try:
            subprocess.run(
                [
                    "pandoc", 
                    "-f", "markdown-smart", 
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