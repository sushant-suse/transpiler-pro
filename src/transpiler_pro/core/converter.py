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
        self.used_ids: Set[str] = set()

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
    
    def _slugify(self, text: str) -> str:
        """
        Converts a heading title into a SEO-friendly, unique ID.
        Example: "Access Keys & Security" -> "access-keys-security"
        """
        # 1. Lowercase and strip technical syntax (like xrefs or inline code)
        slug = text.lower()
        slug = re.sub(r'\{#.*?\}', '', slug) # Remove existing MD IDs
        slug = re.sub(r'[^a-z0-9\s-]', '', slug) # Remove special chars
        
        # 2. Replace spaces/multiple dashes with a single dash
        slug = re.sub(r'[\s_]+', '-', slug).strip('-')
        
        # 3. Handle uniqueness within the document
        base_slug = slug or "section"
        final_slug = base_slug
        counter = 1
        while final_slug in self.used_ids:
            final_slug = f"{base_slug}-{counter}"
            counter += 1
        
        self.used_ids.add(final_slug)
        return final_slug

    def pre_process_markdown(self, content: str) -> str:
        """
        Prepares Markdown for Pandoc by shielding modern syntax and extracting metadata.

        Args:
            content (str): Raw Markdown string.

        Returns:
            str: "Shielded" Markdown ready for Pandoc.
        """
        self.metadata = {}
        self.discovered_title = None
        self.used_ids = set()

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
        # Logic: Priority 1 is YAML 'title'. Priority 2 is the first H1 (#) found.
        self.discovered_title = self.metadata.get('title')
        if not self.discovered_title:
            h1_match = re.search(r'^#\s+(.*)$', content, re.M)
            if h1_match:
                self.discovered_title = h1_match.group(1).strip()
                # Remove the H1 from body as it will be promoted to the AsciiDoc Document Title (=).
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
        
        # Protect existing Markdown IDs so Pandoc doesn't mangle curly braces
        content = re.sub(r'\{#(.*?)\}', r'IDSHIELDSTART\1IDSHIELDEND', content)

        return content

    def post_process_asciidoc(self, content: str) -> str:
        """
        Finalizes the AsciiDoc output after Pandoc has finished.

        This involves:
        1. Restoring shielded blocks (Videos, Tabs, Collapsibles).
        2. Promoting Markdown-style notes to AsciiDoc Admonition blocks.
        3. Normalizing cross-references (xrefs) for the Antora site generator.
        4. Constructing the standard AsciiDoc Header.
        """
        # --- HEADING SLUGGING & NORMALIZATION ---
        def heading_anchor_logic(match):
            level_chars = match.group(1)
            raw_title = match.group(2).strip()
            
            # Check if there is an existing shielded ID
            custom_id_match = re.search(r'IDSHIELDSTART(.*?)IDSHIELDEND', raw_title)
            
            if custom_id_match:
                final_id = custom_id_match.group(1)
                # Remove the shield from the title text
                display_title = raw_title.replace(custom_id_match.group(0), "").strip()
            else:
                final_id = self._slugify(raw_title)
                display_title = raw_title
            
            # Add a leading newline for spacing, then the anchor, then the heading
            return f"\n[#{final_id}]\n{level_chars} {display_title}"

        # Regex: find any heading level 2-6 (AsciiDoc style '==')
        # We process this before any other cleanup to ensure we catch raw Pandoc output
        content = re.sub(r'\n(={2,6})\s+(.*)', heading_anchor_logic, content)
        
        # Final cleanup for any leftover shields
        content = re.sub(r'IDSHIELDSTART.*?IDSHIELDEND', '', content)

        # --- 1. HEADING NORMALIZATION ---
        # Ensure heading levels are consistent (capping at level 5).
        content = re.sub(r'^={6,}\s+', r'===== ', content, flags=re.M)

        # --- 2. MARKER RESTORATION ---
        content = re.sub(r'VIDEOTOKEN([a-zA-Z0-9_-]+)', r'video::\1[youtube]', content)
        # Standardize smart quotes and ellipses
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
            
            # Clean and normalize path: remove extensions and 'inputs/' folder noise
            path = raw_path.replace(".md", "").replace(".adoc", "").replace("./", "").strip("/")
            if "inputs/" in path:
                path = path.split("inputs/")[-1]
            
            if path:
                path = f"{path}.adoc"
                
            # Normalize anchors to AsciiDoc style (lowercase with underscores)
            cl_anchor = ""
            if anchor:
                cl_anchor = "#" + anchor.replace("#", "").lower().replace("-", "-")
            return f"xref:{path}{cl_anchor}"

        # Matches Markdown link syntax and Pandoc-converted AsciiDoc links
        content = re.sub(r'(?:link:|xref:)(?:\+\+)?([^\[\s#\+]+)?(#[^\[\s\+]+)?(?:\+\+)?', antora_xref_logic, content)

        # --- 6. FINAL HEADER CONSTRUCTION ---
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Generate the SEO-friendly slug for the main title
        title_slug = self._slugify(self.discovered_title or "untitled")
        
        # Build the header with the ID and SEO attributes first
        header_lines = [
            f"[#{title_slug}]",
            f"= {self.discovered_title or 'Untitled Document'}",
            ":idprefix:",
            ":idseparator: -"
        ]
        
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
        ready_md = self.pre_process_markdown(raw_md)
        
        # We write to a temporary file so Pandoc sees the 'shielded' version
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md, encoding='utf-8')
        
        try:
            # Execute Pandoc CLI
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
            
            # Post-process the Pandoc result to restore shields and finalize headers
            final_adoc = self.post_process_asciidoc(output_path.read_text(encoding='utf-8'))
            output_path.write_text(final_adoc, encoding='utf-8')
        finally:
            # Tidy up transient files
            if temp_md.exists(): 
                temp_md.unlink()