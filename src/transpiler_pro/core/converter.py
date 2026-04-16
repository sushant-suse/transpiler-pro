"""
Location: src/transpiler_pro/core/converter.py
Description: The Structural Transformation Engine (X-Phase).

This module orchestrates the conversion of Markdown (MD/MDX) into AsciiDoc (ADOC).
It uses a "Shield-Pandoc-Restore" sandwich architecture:
1. Pre-processing: Shielding complex Markdown (Tabs, Collapsibles, Videos) so 
   Pandoc doesn't mangle them.
2. Pandoc: Performing the baseline structural conversion.
3. Post-processing: Restoring shielded blocks, promoting admonitions, and 
   standardizing Antora-compatible cross-references and headers.
"""

import re
import subprocess
import yaml
from datetime import datetime
from pathlib import Path
from typing import Match, Optional, Dict, Any

class DocConverter:
    """
    A pattern-driven engine that transforms Markdown into Enterprise AsciiDoc.
    
    Attributes:
        config (Dict): Configuration extracted from pyproject.toml.
        metadata (Dict): Extracted frontmatter (YAML) from the source file.
        discovered_title (str): The inferred document title (H1 or YAML).
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initializes the converter and loads conversion patterns."""
        self.config_path = config_path or Path("pyproject.toml")
        self.config = self._load_project_config()
        self.conv_cfg = self.config.get("conversions", {})
        self.metadata: Dict[str, Any] = {}
        self.discovered_title = None
        # registry: Dict[str, str] = {}

    def _load_project_config(self) -> Dict[str, Any]:
        """Loads the [tool.transpiler-pro] configuration block."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                import tomllib
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}

    def pre_process_markdown(self, content: str) -> tuple[str, dict]:
        """
        Prepares Markdown for Pandoc by shielding modern syntax and extracting metadata.

        Args:
            content (str): Raw Markdown string.

        Returns:
            tuple[str, dict]: A tuple containing the "shielded" Markdown ready for Pandoc and the extracted metadata.
        """
        self.metadata = {}
        self.discovered_title = None
        # Use a clear local name for the registry we will return
        local_registry = {} 

        # --- 0. PRECISION JSX SHIELDING ---
        target_components = ["JsonDisplay", "TriggerPayload", "CircuitDisplay"]
        for tag_name in target_components:
            search_pos = 0
            while True:
                # Find the EXACT start of the tag
                start_tag = content.find(f"<{tag_name}", search_pos)
                if start_tag == -1: break
                
                # Find the matching balanced closing tag
                end_tag = -1
                potential_end = start_tag
                while True:
                    potential_end = content.find("/>", potential_end + 1)
                    if potential_end == -1: break
                    
                    # Capture the full string including the closing '/>'
                    test_chunk = content[start_tag : potential_end + 2]
                    # BALANCE CHECK: Ensure all JSON braces are inside this chunk
                    if test_chunk.count("{") == test_chunk.count("}"):
                        end_tag = potential_end + 2
                        break
                
                if end_tag == -1:
                    search_pos = start_tag + 1
                    continue
                
                # --- LITERAL CAPTURE ---
                # We grab the EXACT substring from the original content
                full_block = content[start_tag : end_tag]
                
                index = len(local_registry)
                marker = f"RESTORE_COMPONENT_TOKEN_{index}Z"
                local_registry[marker] = full_block
                
                # --- LITERAL REPLACEMENT ---
                # We replace that EXACT range with the marker
                content = content[:start_tag] + marker + content[end_tag:]
                
                # Move search position forward
                search_pos = start_tag + len(marker)

        # DEBUG PASS 1: Confirm shielding count
        print(f"[DEBUG 1] Phase-X Shielding: Found {len(local_registry)} components in current file.")

        # --- 1. CODE BLOCK SHIELDING ---
        # We protect '#' characters inside code blocks so the Title Scavenger 
        # doesn't accidentally treat a code comment as the document's H1 title.
        content = re.sub(r'(`{3}.*?`{3})', lambda m: m.group(1).replace('#', 'HASHSHIELD'), content, flags=re.DOTALL)

        # --- 2. FRONTMATTER EXTRACTION ---
        # Extracts YAML metadata (title, description, etc.) from the top of the MD file.
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            try:
                yaml_data = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(yaml_data, dict):
                    self.metadata = yaml_data
                content = content[frontmatter_match.end():]
            except Exception:
                self.metadata = {}

        # --- 3. TITLE SCAVENGER ---
        self.discovered_title = self.metadata.get('title')
        # Even if we have a YAML title, we MUST find and remove the H1 from the body
        # to prevent "Duplicate Title" noise in the audit.
        h1_match = re.search(r'^#\s+(.*)$', content, re.M)
        if h1_match:
            if not self.discovered_title:
                self.discovered_title = h1_match.group(1).strip()
            # Always remove the H1 line from the body content
            content = content.replace(h1_match.group(0), "", 1)

        # Restore shielded hashes after title scavenging is safe.
        content = content.replace('HASHSHIELD', '#')

        # --- 4. VIDEO & COMPLEX PATTERN SHIELDING ---
        # Replaces complex HTML/Markdown blocks with tokens that Pandoc will ignore.
        # This protects <iframe> embeds and custom ':::tabs' blocks.
        content = re.sub(r'<iframe.*?embed/([^"?\s]+).*?</iframe>', r'VIDEOTOKEN\1', content)

        patterns = self.conv_cfg.get("shielding_patterns", [])
        for p in patterns:
            regex = p.get("regex")
            replacement = p.get("replacement")
            
            if p.get("hook") == "protect_spaces":
                # Special hook for collapsibles to ensure spaces in titles aren't lost.
                def protect_hook(match: Match) -> str:
                    title = match.group(1).strip().replace(' ', 'PROTECTSPACE')
                    body = match.group(2).strip()
                    return replacement.replace(r"\1", title).replace(r"\2", body)
                content = re.sub(regex, protect_hook, content, flags=re.S)
            else:
                content = re.sub(regex, replacement, content, flags=re.S)
        
        return content, local_registry

    def post_process_asciidoc(self, content: str, registry: dict) -> str:
        """
        Finalizes the AsciiDoc output after Pandoc has finished.

        This involves:
        1. Restoring shielded blocks (Videos, Tabs, Collapsibles, Components, URLs).
        2. Promoting Markdown-style notes to AsciiDoc Admonition blocks.
        3. Normalizing cross-references (xrefs) for the Antora site generator.
        4. Constructing the standard AsciiDoc Header.
        """
        # DEBUG PASS 2: Confirm registry arrival
        print(f"[DEBUG 2] Phase-X Restoration: Registry received with {len(registry)} keys.")

        # Sort by length descending to prevent _10 being hit by _1
        sorted_keys = sorted(registry.keys(), key=len, reverse=True)
        restore_count = 0
        
        for marker in sorted_keys:
            original_value = registry[marker]
            
            # 1. Try Literal Match first (Fastest)
            if marker in content:
                content = content.replace(marker, original_value)
                restore_count += 1
                continue

            # 2. Try the "Pandoc-Safe" Regex
            # This handles: `TOKEN`, +TOKEN+, TOKEN with escaped underscores, 
            # or TOKEN broken by line wraps.
            # We break the marker into parts: ['RESTORE', 'COMPONENT', 'TOKEN', '0Z']
            parts = marker.split('_')
            # This regex allows for backslashes, spaces, or underscores between words
            regex_pattern = r"[`\+\^]*" + r"[\\\_]*".join(map(re.escape, parts)) + r"[`\+\^]*"
            
            if re.search(regex_pattern, content):
                content = re.sub(regex_pattern, original_value, content)
                restore_count += 1
                continue
            
            # 3. Final "Fuzzy" Fallback
            # If the token is 'RESTORE_COMPONENT_TOKEN_0Z', we look for 'RESTORE' ... '0Z'
            fuzzy_pattern = re.escape(parts[0]) + r".*?" + re.escape(parts[-1])
            match = re.search(fuzzy_pattern, content)
            if match and "RESTORE" in match.group(0):
                content = content.replace(match.group(0), original_value)
                restore_count += 1

        print(f"[DEBUG 3] Phase-X Restoration: Successfully swapped {restore_count} markers back to data.")

        # --- 1. HEADING NORMALIZATION ---
        content = re.sub(r'^={6,}\s+', r'===== ', content, flags=re.M)

        # --- 2. MARKER RESTORATION ---
        content = re.sub(r'VIDEOTOKEN([a-zA-Z0-9_-]+)', r'video::\1[youtube]', content)
        content = content.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('…', '...')

        # Apply cleanup regex from pyproject.toml
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

        # --- 3. ADMONITION PROMOTION ---
        # Converts phrases like "Note: content" or "*Warning:* content" into [NOTE] blocks.
        def promote_admo(match: Match) -> str:
            label = match.group(1).upper()
            body = match.group(2).strip()
            return f"[{label}]\n====\n{body}\n===="
        
        content = re.sub(r'(?i)^\*?(Note|Warning|Tip|Caution|Important|IMPORTANT)[:]?\*?[:]?\s+(.*)$', promote_admo, content, flags=re.M)

        # --- 4. DYNAMIC MARKER RESTORATION ---
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

        # --- 5. ANTORA NORMALIZATION (Links & Images) ---
        # Clean image paths (stripping the /images/ prefix used in Markdown)
        content = re.sub(r'image::/images/(.*?)\[', r'image::\1[', content)
        
        def antora_xref_logic(match: Match) -> str:
            """Converts Markdown links into Antora-compatible xrefs."""
            raw_path = match.group(1) or ""
            anchor = match.group(2) or ""

            # Clean Pandoc mangle from path and anchor
            raw_path = raw_path.replace("++_++", "_")
            anchor = anchor.replace("++_++", "_")
            
            # Clean and normalize path: remove extensions and 'inputs/' folder noise
            path = raw_path.replace(".md", "").replace(".adoc", "").replace("./", "").strip("/")
            if "inputs/" in path:
                path = path.split("inputs/")[-1]
            
            if path:
                path = f"{path}.adoc"
                
            # Normalize anchors to AsciiDoc style (lowercase with underscores)
            cl_anchor = ""
            if anchor:
                cl_anchor = "#_" + anchor.replace("#", "").lower().replace("-", "_")
            return f"xref:{path}{cl_anchor}"

        # Matches Markdown link syntax and Pandoc-converted AsciiDoc links
        content = re.sub(r'(?:link:|xref:)(?:\+\+)?([^\[\s#\+]+)?(#[^\[\s\+]+)?(?:\+\+)?', antora_xref_logic, content)

        # --- 6. FINAL HEADER CONSTRUCTION ---
        today = datetime.now().strftime("%Y-%m-%d")
        header_lines = [f"= {self.discovered_title or 'Untitled Document'}"]
        
        # Inject YAML metadata as AsciiDoc attributes
        for key, value in self.metadata.items():
            if key.lower() != "title":
                header_lines.append(f":{key}: {value}")
        
        header_lines.append(f":revdate: {today}")
        
        # Add global Antora headers from pyproject.toml
        antora_cfg = self.config.get("antora", {})
        header_lines.extend(antora_cfg.get("headers", []))
        
        header_block = "\n".join(header_lines) + "\n\n"
        
        # --- 7. CLEANUP & EXTENSION CONVERSION ---
        # Final cleanup for Mermaid diagrams and Tab syntax
        content = re.sub(r'\[source,mermaid\]\n----(.*?)----', r'[mermaid]\n....\1....', content, flags=re.DOTALL)
        content = content.replace("SHIELDADMONSTARTtabs", "[tabs]\n====")
        content = content.replace("SHIELDADMONEND", "====")
        content = re.sub(r'^@tab\s+(.*)$', r'\1::', content, flags=re.M)
        
        # --- 8. TECHNICAL URL RECOVERY ---
        # Fixes the specific chopping of the ssoDomain endpoint
        content = re.sub(r'([a-zA-Z0-9])\?(\s|$)', r'\1?email=`\2', content)

        return header_block + content.strip()
    
    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """
        Orchestrates the conversion of a single Markdown file to AsciiDoc.
        
        Args:
            input_path (Path): Source Markdown file.
            output_path (Path): Destination for the raw AsciiDoc.
        """
        self.metadata = {}
        self.discovered_title = None
        
        raw_md = input_path.read_text(encoding='utf-8')
        # Capture the local_registry specifically for this file
        ready_md, local_registry = self.pre_process_markdown(raw_md)
        
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
            
            # Inject the specific registry into the post-processor
            final_adoc = self.post_process_asciidoc(output_path.read_text(encoding='utf-8'), local_registry)
            output_path.write_text(final_adoc, encoding='utf-8')
        finally:
            if temp_md.exists(): 
                temp_md.unlink()
