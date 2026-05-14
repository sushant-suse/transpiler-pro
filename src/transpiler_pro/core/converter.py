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
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Set, List

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
        self.protected_json: List[str] = []
        self.heading_vault = {}
        # Set to True to replace brand names with {attributes}
        self.REPLACE_WITH_ATTRIBUTES = True

        # --- SUSE Branding Attribute Map ---
        # Format: "Exact Text to find": "{attribute-variable}"
        self.attribute_map = {
            "Losant": "{losant-product-name}",
            # Add other SUSE mappings here...
        }

    def _load_project_config(self) -> Dict[str, Any]:
        """Loads the [tool.transpiler-pro] configuration block.
        
        Args:
            config_path (Path): Path to the pyproject.toml file.
            
        Returns:
            Dict: The configuration dictionary for transpiler-pro.
        """
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                import tomllib
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}
    

    def _apply_global_attributes(self, text: str) -> str:
        """
        Replaces raw product names with Antora attributes.
        Uses negative lookbehind/lookahead to protect URLs and file paths.

        Args:
            text (str): The input string to process.

        Returns:
            str: The text with product names replaced by attributes.
        """
        # Guard clause: If text is empty or if attribute replacement is disabled, return the original text.
        if not text or not self.REPLACE_WITH_ATTRIBUTES:
            return text
        
        # We iterate through the attribute map and apply replacements. 
        # The regex ensures we only replace standalone occurrences of the product names, 
        # not when they are part of URLs or file paths.        
        for raw_name, attr in self.attribute_map.items():
            # SMART REGEX:
            # (?<![/:]) -> Negative Lookbehind: Don't match if preceded by / or : (Shields paths/URLs)
            # \b...\b   -> Word Boundary: Match the whole word only
            # (?![/.])  -> Negative Lookahead: Don't match if followed by / or . (Shields extensions/paths)
            pattern = rf"(?<![/:])\b{re.escape(raw_name)}\b(?![/.])"
            
            text = re.sub(pattern, attr, text)

        return text
    
    
    def _slugify(self, text: str) -> str:
        """
        Converts a heading title into a SEO-friendly, unique ID.

        Args:
            text (str): The heading text to slugify.
        Returns:
            str: A slugified version of the heading, suitable for use as an ID.
        """
        # Guard clause for empty text to prevent generating empty IDs
        lookup_key = text.strip()
        
        if "VLT" in lookup_key and "HVAULT" in lookup_key:
            if hasattr(self, 'heading_vault') and lookup_key in self.heading_vault:
                text = self.heading_vault[lookup_key]

        # 1. Strip raw HTML tags (if any survived)
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # 2. Strip AsciiDoc roles (e.g., [.class-name]#Text#)
        clean_text = re.sub(r'\[\.[^\]]+\]#.*?#', '', clean_text)
        
        # 3. Normalize to lowercase and replace spaces with hyphens
        slug = clean_text.lower()
        
        # 4. Remove any remaining curly brace IDs and replace dots with hyphens
        slug = re.sub(r'\{#.*?\}', '', slug) 
        slug = slug.replace('.', '-')
        slug = re.sub(r'[^a-z0-9-]', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        
        # 5. Ensure uniqueness by appending a counter if needed
        base_slug = slug or "section"
        final_slug = base_slug
        
        counter = 1

        # 6. If the slug already exists, append a counter until we find a unique one
        while final_slug in self.used_ids:
            final_slug = f"{base_slug}-{counter}"
            counter += 1
        
        # 7. Register the final slug to prevent future collisions
        self.used_ids.add(final_slug)

        return final_slug


    def pre_process_markdown(self, content: str) -> str:
        """
        Prepares Markdown for Pandoc by shielding modern syntax and extracting metadata.
        Includes a 'Vault' mechanism to protect version headers from line-splitting.

        Args:
            content (str): Raw Markdown string.

        Returns:
            str: "Shielded" Markdown ready for Pandoc.
        """
        self.metadata = {}
        self.discovered_title = None
        self.used_ids = set()
        self.protected_json = []
        self.heading_vault = {}

        def vault_header(m: re.Match) -> str:
            """
            Protects version headers like "## 2.2.0 - 2026-03-23" from being split by the list item regex.

            Args:
                m: The regex match object for a version header.
            """
            # We store the raw header text in a vault and replace it with a unique key.
            level = m.group(1)

            # We want to preserve the exact text of the header, including the version and date, so we store it in the vault.
            raw_text = m.group(2).strip()

            # We generate a unique key for this header and store the raw text in the vault under that key.
            key = f"VLT{len(self.heading_vault)}HVAULT"

            # We store the raw header text in the vault using the unique key.
            self.heading_vault[key] = raw_text

            return f"{level} {key}"

        # Secure the version headers before anything else touches them
        # We look for headers that start with ## (or more) followed by a version pattern and a date, and we vault them.
        pattern = r'^(#+)\s+(\d+\.[\d\.]+\d+\s+-\s+\d{4}-\d{2}-\d{2}).*$'
        # We replace the matched header with a vault key, and store the original header text 
        # in the heading_vault for later restoration.
        content = re.sub(pattern, vault_header, content, flags=re.M)

        # --- EXISTING SHIELDING LOGIC ---
        # 1. Code Blocks: Shield fenced code blocks to prevent Pandoc from mangling them.
        content = re.sub(r'(`{3}.*?`{3})', lambda m: m.group(1).replace('#', 'HASHSHIELD'), content, flags=re.DOTALL)
        # 2. Inline Code: Shield inline code to prevent accidental ID processing.
        content = re.sub(r'(`.*?`)', lambda m: m.group(1).replace('#', 'HASHSHIELD'), content)

        # 3. Iframes: Temporarily replace iframes with a token to prevent Pandoc from stripping them.
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)

        # 4. Custom Shielding Patterns: Apply any user-defined regex patterns for shielding.
        if frontmatter_match:
            try:
                import yaml

                # We attempt to parse the frontmatter as YAML to extract metadata. 
                # If successful, we store it in self.metadata.
                # If the frontmatter is not valid YAML, we catch the exception and simply leave 
                # self.metadata as an empty dictionary, allowing the conversion to proceed without metadata.
                yaml_data = yaml.safe_load(frontmatter_match.group(1))

                # We check if the parsed YAML data is a dictionary before assigning it to self.metadata.
                if isinstance(yaml_data, dict):
                    self.metadata = yaml_data

                # If a title is found in the metadata, we can remove it from the content to prevent duplication.
                content = content[frontmatter_match.end():]
            except Exception:
                # If YAML parsing fails, we simply ignore the frontmatter and proceed with an empty metadata dictionary.
                self.metadata = {}

        # 5. Title Discovery: If no title is in metadata, infer from the first H1 and remove it from content.
        self.discovered_title = self.metadata.get('title')

        # We look for the first H1 header in the content to use as the title if it wasn't provided in the metadata.
        if not self.discovered_title:
            # We search for a line that starts with a single '#' followed by the title text.
            h1_match = re.search(r'^#\s+(.*)$', content, re.M)

            # If we find an H1 header, we set it as the discovered title and remove that line 
            # from the content to prevent duplication in the final AsciiDoc.
            if h1_match:
                self.discovered_title = h1_match.group(1).strip()
                # We remove the first occurrence of this H1 header from the content.
                content = content.replace(h1_match.group(0), "", 1)

        # --- 6. HTML SHIELDING ---
        self.protected_html_blocks = []
        def shield_html_block(match):
            placeholder = f"HTMLBLOCKSHIELDA{len(self.protected_html_blocks)}A"
            self.protected_html_blocks.append(match.group(1))
            return placeholder
        
        # Shield entire <style> or <script> blocks so Pandoc ignores their contents
        content = re.sub(r'(<style.*?</style>)', shield_html_block, content, flags=re.DOTALL|re.IGNORECASE)

        # Additionally, we will shield structural HTML tags like <div>, <ul>, and <li> to prevent Pandoc from stripping them.
        self.protected_html_tags = []

        # 7. Shielding Structural HTML Tags: We define a function to shield structural HTML tags like <div>, <ul>, and <li>.
        def shield_layout_tag(match: re.Match) -> str:
            """
            Shields structural HTML tags like <div>, <ul>, and <li> to prevent Pandoc from stripping them.
            Uses a vault mechanism similar to the version headers to store the original tag content and 
            replace it with a unique placeholder. This allows us to restore the exact original HTML tags after Pandoc processing,
            without risking any regex collisions or unintended replacements.

            The placeholder format is designed to be unique and easily identifiable for restoration in the post-processing phase 
            without interfering with any other content. By using a vault, we can ensure that even if the same HTML tag appears multiple times, 
            each instance will be stored and restored correctly without any risk of collision or misreplacement.   

            Args:
                match: The regex match object for an HTML tag to be shielded.

            Returns:
                str: A unique placeholder string that will be used in the content to represent the original HTML tag. 
            """
            placeholder = f"HTMLTAGSHIELDA{len(self.protected_html_tags)}A"
            self.protected_html_tags.append(match.group(1))
            return placeholder

        # 8a. Shield structural tags (div, ul, li) but let Pandoc handle <span> natively
        content = re.sub(r'(</?(?:div|ul|li)[^>]*>)', shield_layout_tag, content, flags=re.IGNORECASE)

        # 8b. Shield <kbd> tags safely without applying HTML passthroughs (+++)
        content = re.sub(r'(?i)<kbd>', 'KBDSHIELDSTART', content)
        content = re.sub(r'(?i)</kbd>', 'KBDSHIELDEND', content)

        # Ensure that we shield any custom patterns defined in the configuration, such as collapsibles or tabs, 
        # before Pandoc sees them.
        content = content.replace('HASHSHIELD', '#')
        content = re.sub(r'<iframe.*?embed/([^"?\s]+).*?</iframe>', r'VIDEOTOKEN\1', content)

        # Process any additional user-defined shielding patterns from the configuration file. 
        # This allows for flexible extension of the shielding mechanism to accommodate various custom Markdown 
        # constructs that may not be natively supported by Pandoc.
        patterns = self.conv_cfg.get("shielding_patterns", [])

        # 9. We iterate through the list of shielding patterns defined in the configuration. 
        # Each pattern is expected to have a "regex" to match,
        for p in patterns:
            # a "replacement" string that defines how to transform the matched content, 
            # and optionally a "hook" that specifies
            regex = p.get("regex")
            replacement = p.get("replacement")
            if p.get("hook") == "protect_spaces":
                def protect_hook(match: re.Match) -> str:
                    """
                    Function to protect spaces in titles by replacing them with a placeholder. 
                    This is necessary to prevent Pandoc from collapsing multiple spaces into one, 
                    which can cause issues with certain formatting or when the title is used as an ID.

                    Args:
                        match: The regex match object containing the title and body to be protected.

                    Returns:
                        str: The replacement string with spaces in the title protected by a placeholder.
                    """
                    title = match.group(1).strip().replace(' ', 'PROTECTSPACE')
                    body = match.group(2).strip()
                    return replacement.replace(r"\1", title).replace(r"\2", body)
                content = re.sub(regex, protect_hook, content, flags=re.S)
            else:
                content = re.sub(regex, replacement, content, flags=re.S)
        
        # 10. Finally, we shield JSON components like <JsonDisplay> to prevent any Pandoc interference, 
        # using the same vault mechanism for safe restoration later.
        def shield_json_display(match: re.Match) -> str:
            """Shields <JsonDisplay> components to prevent Pandoc from mangling them. 
            Uses a vault mechanism to store the original JSON content and replace it with a unique placeholder. 

            Args:
                match: The regex match object for a <JsonDisplay> component.
            
            Returns:
                str: A unique placeholder string that will be used in the content to represent the original <JsonDisplay> component.
            """
            placeholder = f"JSONP{len(self.protected_json)}PROTECT"
            self.protected_json.append(match.group(1))
            return placeholder

        # 11. We apply the shielding function to any <JsonDisplay> components found in the content, 
        # ensuring that they are safely stored and replaced with unique placeholders before Pandoc processing.
        content = re.sub(r'(<JsonDisplay.*?\/>)', shield_json_display, content, flags=re.DOTALL)
        
        # Protect HTML comments from being deleted by Pandoc
        # We concatenate the pattern so Markdown parsers don't hide it as a real comment!
        comment_pattern = r'<' + r'!--(.*?)-->'
        content = re.sub(comment_pattern, lambda m: f"HTMLCOMMENTSHIELD{m.group(1)}HTMLCOMMENTEND", content, flags=re.DOTALL)

        # Shield custom IDs {#id}, but use a Negative Lookbehind (?<!\{) 
        # so we DO NOT accidentally capture Handlebars block helpers like {{#if}}
        content = re.sub(r'(?<!\{)\{#(.*?)\}', r'IDSHIELDSTART\1IDSHIELDEND', content)

        return content
    

    def post_process_asciidoc(self, content: str) -> str:
        """
        Restores shielded content, promotes admonitions, and finalizes headers in the AsciiDoc output.
            - Heading Anchors: Converts headers to Antora-compatible format with unique IDs.
            - The Cloak: Restores version headers that were vaulted to protect them from regex collisions.
            - HTML Restoration: Restores shielded HTML blocks and tags as passthroughs.
            - Cleanup & Metadata: Applies final regex cleanups and constructs the AsciiDoc header block with metadata.
        
        Args:
            content (str): The raw AsciiDoc output from Pandoc.
        
        Returns:
            str: The final, polished AsciiDoc content ready for Antora.
        """
        # Guard clause for empty content to avoid unnecessary processing.
        self.used_ids = set() 
        today = datetime.now().strftime("%Y-%m-%d")

        # --- GLOBAL BUILD FLAGS ---
        # --- 1. ID STRATEGY TOGGLE ---
        # Set to True for SUSE-style [#id] shorthand
        # Set to False for long-form [id="id"]
        USE_SUSE_SHORTHAND = True
        # --- 2. DAPS COMPATIBILITY MODE ---
        DAPS_COMPATIBILITY_MODE = True

        def smart_id_format(final_id: str) -> str:
            """
            Always uses long-form [id="..."] if a dot exists to prevent build errors.
            Otherwise, respects the USE_SUSE_SHORTHAND flag.

            Args:
                final_id (str): The ID to format.

            Returns:
                str: The formatted ID block for AsciiDoc.
            """
            if USE_SUSE_SHORTHAND and "." not in final_id:
                return f"[#{final_id}]"
            return f'[id="{final_id}"]'
        
        # If the discovered title is something generic like "Untitled Document", 
        # we won't slugify it to avoid generating an unhelpful ID.
        title_slug = self._slugify(self.discovered_title or "untitled")
        title_text = self._apply_global_attributes(self.discovered_title or "Untitled Document")

        # --- 1. HEADING SLUGGING & NORMALIZATION ---
        def heading_anchor_logic(match: re.Match) -> str:
            """
            Converts Markdown headers into Antora-compatible AsciiDoc headers with unique IDs.

            Args:
                match: The regex match object for a header line, containing the header level and text.

            Returns:
                str: The transformed header line with an Antora-compatible ID block.
            """
            # We extract the header level characters (e.g., "==") and the raw title text from the matched header line.
            level_chars = match.group(1)
            raw_title = match.group(2).strip()
            
            # We check if the raw title contains a custom ID shield (IDSHIELDSTART...IDSHIELDEND). 
            # If it does, we extract the base ID from within the shield and use it as the final ID.
            custom_id_match = re.search(r'IDSHIELDSTART(.*?)IDSHIELDEND', raw_title)

            # If a custom ID is found, we use it directly. If not, we generate a slug from the raw title text.
            if custom_id_match:
                # We extract the base ID from the custom ID shield and use it as the final ID for this header.
                base_id = custom_id_match.group(1)

                # We also clean the display title by removing the custom ID shield from the raw title, 
                # ensuring that the header text is clean and free of any ID artifacts.
                display_title = raw_title.replace(custom_id_match.group(0), "").strip()

                # We must also ensure that the final ID is unique across the document. 
                # If the base ID already exists in self.used_ids, we append a counter to it until we find a unique ID, 
                # and then we register that final ID in self.used_ids to prevent future collisions.
                final_id = base_id
                
                counter = 1

                # If the final ID already exists, we append a counter until we find a unique one.
                while final_id in self.used_ids:
                    final_id = f"{base_id}-{counter}"
                    counter += 1
                self.used_ids.add(final_id)
            else:
                # If no custom ID is found, we generate a slug from the raw title text to use as the final ID for this header.
                final_id = self._slugify(raw_title)
                display_title = raw_title

            # We apply global attribute replacements to the display title to ensure that any product names are 
            # replaced with their corresponding Antora attributes,
            display_title = self._apply_global_attributes(display_title)
            
            # Use the Smart Formatter to choose between [#id] and [id="id"]
            id_block = smart_id_format(final_id)
            
            # Ensure only ONE return statement exists here
            return f'\n{id_block}\n{level_chars} {display_title}'

        # Prepend a temporary newline to guarantee the absolute first line is caught
        content = "\n" + content

        # Apply anchors to headers (Horizontal space [^\S\r\n]+ protects ==== admonition blocks)
        content = re.sub(r'\n(={2,6})[^\S\r\n]+([^\n]+)', heading_anchor_logic, content)

        # --- 2. THE CLOAK ---
        if hasattr(self, 'heading_vault'):
            # We iterate through the heading vault and replace each unique key in the content with its original raw header text, 
            # restoring the version headers that were protected from regex collisions during processing.
            for key, real_text in self.heading_vault.items():
                # Replace the literal hyphen with an HTML entity
                # repair.py won't see it, but AsciiDoc will render it perfectly.
                cloaked_text = real_text.replace(" - ", " &#45; ")
                content = content.replace(key, cloaked_text)
        
        # Restore JSON Components
        if hasattr(self, 'protected_json'):
            # We iterate through the list of protected JSON components and replace each unique placeholder in the content 
            # with its original JSON content, ensuring that all <JsonDisplay> components are fully restored to their original form 
            # after Pandoc processing.
            for i, original in enumerate(self.protected_json):
                content = content.replace(f"JSONP{i}PROTECT", original)

        # --- 3. RESTORE HTML ---
        # Restore <style> as a block passthrough
        if hasattr(self, 'protected_html_blocks'):
            for i, original in enumerate(self.protected_html_blocks):
                # Wrap in ++++ so AsciiDoc renders the raw CSS block
                content = content.replace(f"HTMLBLOCKSHIELDA{i}A", f"++++\n{original}\n++++")
                
        # Restore <div>, <ul>, <li> as inline passthroughs
        if hasattr(self, 'protected_html_tags'):
            for i, original in enumerate(self.protected_html_tags):
                # Wrap in +++ so AsciiDoc renders the raw tag
                content = content.replace(f"HTMLTAGSHIELDA{i}A", f"+++{original}+++")

        # --- 4. CLEANUP & METADATA ---
        content = re.sub(r'IDSHIELDSTART.*?IDSHIELDEND', '', content)
        content = self._apply_global_attributes(content)

        # UI MACROS (Keyboard)
        # 1. Convert KBD shields to AsciiDoc kbd:[] macros
        content = re.sub(r'KBDSHIELDSTART(.*?)KBDSHIELDEND', r'kbd:[\1]', content)
        
        # 2. Merge adjacent kbd macros separated by a plus OR Pandoc's {plus}
        content = re.sub(r'kbd:\[([^\]]+)\]\s*(?:\+|\{plus\})\s*kbd:\[([^\]]+)\]', r'kbd:[\1+\2]', content)
        content = re.sub(r'kbd:\[([^\]]+)\]\s*(?:\+|\{plus\})\s*kbd:\[([^\]]+)\]', r'kbd:[\1+\2]', content)

        # Header Block: Uses the same smart ID logic for the Title
        main_heading = "==" if DAPS_COMPATIBILITY_MODE else "="
        header_lines = [
            smart_id_format(title_slug),
            f"{main_heading} {title_text}",
            ":idprefix:",
            ":idseparator: -"
        ]

        # Inject doctype (defaults to 'article' if not set via CLI)
        doctype = getattr(self, 'doctype', 'article')
        if doctype != 'article':
            header_lines.append(f":doctype: {doctype}")

        # Inject the experimental flag if UI macros like kbd:[] are detected in the content
        if "kbd:[" in content:
            header_lines.append(":experimental:")
        
        # Apply branding attributes to metadata values as well
        for key, value in self.metadata.items():
            if key.lower() == "title":
                continue

            # Check the Master Toggle first
            if not self.REPLACE_WITH_ATTRIBUTES:
                header_lines.append(f":{key}: {value}")
                continue

            # CASE A: The value is a simple String (like Description)
            if isinstance(value, str):
                processed_value = self._apply_global_attributes(value)
                header_lines.append(f":{key}: {processed_value}")

            # CASE B: The value is a List (like Keywords)
            elif isinstance(value, list):
                # We process every string inside the list
                processed_list = [
                    self._apply_global_attributes(item) if isinstance(item, str) else item 
                    for item in value
                ]
                header_lines.append(f":{key}: {processed_list}")

            # CASE C: Anything else (numbers, booleans)
            else:
                header_lines.append(f":{key}: {value}")
        
        # We add a revdate attribute with today's date to the header block, 
        # which can be used in Antora for versioning or display purposes.
        header_lines.append(f":revdate: {today}")
        
        # We also include any additional header lines defined in the Antora configuration under the "headers" key, 
        # allowing for flexible customization of the AsciiDoc header block based on user-defined settings.
        antora_cfg = self.config.get("antora", {})
        header_lines.extend(antora_cfg.get("headers", []))
        header_block = "\n".join(header_lines) + "\n\n"

        # We prepend the constructed header block to the content, ensuring that the final AsciiDoc output includes 
        # all necessary metadata and formatting directives at the top of the document.
        if hasattr(self, 'protected_json'):
            for i, original in enumerate(self.protected_json):
                content = content.replace(f"JSONP{i}PROTECT", original)

        # We perform some final cleanups to replace any temporary placeholders with their intended characters,
        # such as "++_++" back to "_", and to standardize quotes and ellipses, ensuring that the final content is polished 
        # and free of any artifacts from the shielding process before returning it as the final output.
        content = content.replace("++_++", "_").replace("++{++", "{").replace("++}++", "}")
        content = content.replace("++{{++", "{{").replace("++}}++", "}}")
        content = content.replace("++<++", "<").replace("++>++", ">")
        content = content.replace("++*++", "*").replace("++_++", "_")
        content = re.sub(r'VIDEOTOKEN([a-zA-Z0-9_-]+)', r'video::\1[youtube]', content)
        content = content.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('…', '...')

        # Finally, we apply any user-defined cleanup regex patterns from the configuration file, 
        # allowing for flexible post-processing adjustments to the content based on specific needs or 
        # preferences defined in the configuration.
        cleanup = self.conv_cfg.get("cleanup_regex", [])
        for c in cleanup:
            # We check if the regex pattern has a "flags" key set to "M" for multiline; 
            # if so, we set the flags variable accordingly.
            flags = re.M if c.get("flags") == "M" else 0

            if c.get("hook") == "uppercase_label":
                # This hook is designed to promote certain labels (like Note, Warning, Tip) to uppercase and 
                # format them as AsciiDoc admonitions.
                def uppercase_hook(m: re.Match) -> str:
                    """
                    Function to promote labels like Note, Warning, Tip to uppercase and format them as AsciiDoc admonitions.

                    Args:
                        m: The regex match object containing the label and body to be promoted.
                    
                    Returns:
                        str: The replacement string formatted as an AsciiDoc admonition with the label in uppercase.
                    """
                    return f"[{m.group(1).upper()}]\n====\n{m.group(2).strip()}\n===="

                # We apply the uppercase_label hook to the content using the provided regex pattern, 
                # transforming matched labels into uppercase and formatting them as AsciiDoc admonitions.
                content = re.sub(c.get("regex"), uppercase_hook, content, flags=flags)
            else:
                # For any other cleanup patterns that don't have a specific hook, 
                # we apply a standard regex substitution using the provided pattern and replacement string, 
                # allowing for flexible cleanup operations based on user-defined configurations.
                content = re.sub(c.get("regex"), c.get("replacement"), content, flags=flags)

        # --- 5. PROMOTE ADMONITIONS ---
        def promote_admo(m: re.Match) -> str:
            """
            Promotes labels like Note, Warning, Tip to uppercase and formats them as AsciiDoc admonitions.

            Args:
                m: The regex match object containing the label and body to be promoted.
            
            Returns:
                str: The replacement string formatted as an AsciiDoc admonition with the label in uppercase.
            """
            return f"[{m.group(1).upper()}]\n====\n{m.group(2).strip()}\n===="
        
        # We apply the promote_admo function to any lines in the content that match the pattern for Note, Warning, Tip, Caution, or Important labels,
        # promoting them to uppercase and formatting them as AsciiDoc admonitions, ensuring that these important labels are visually distinct and properly formatted in the final output.   
        content = re.sub(r'(?i)^\*?(Note|Warning|Tip|Caution|Important|IMPORTANT)[:]?\*?[:]?\s+(.*)$', promote_admo, content, flags=re.M)

        # --- 6. RESTORE SHIELDED BLOCKS ---
        restorations = self.conv_cfg.get("restoration_patterns", [])

        # We iterate through the list of restoration patterns defined in the configuration. 
        # Each pattern is expected to have a "regex" to match, a "replacement" string that defines 
        # how to transform the matched content, and optionally a "hook" that specifies a custom function to handle the restoration logic for that pattern.
        for r in restorations:
            # We check if the restoration pattern has a specific hook defined for restoring spaces in titles.
            if r.get("hook") == "restore_spaces":

                def restore_hook(m: re.Match) -> str:
                    """
                    Function to restore spaces in titles that were previously protected by a placeholder.

                    Args:
                        m: The regex match object containing the title and body to be restored.
                    Returns:
                        str: The replacement string with spaces in the title restored from the placeholder.
                    """
                    # We extract the full block of text that contains the title and body, 
                    # which is expected to be separated by "SHIELDSEP" or a newline.
                    full_block = m.group(1)

                    # We split the full block into title and body parts based on the "SHIELDSEP" delimiter.
                    parts = full_block.split("SHIELDSEP", 1) if "SHIELDSEP" in full_block else full_block.split("\n", 1)

                    # We restore spaces in the title by replacing the "PROTECTSPACE" placeholder with actual spaces, 
                    # and we also strip any leading or trailing whitespace.  
                    title = parts[0].replace('PROTECTSPACE', ' ').strip()

                    # We take the body part (if it exists) and strip leading/trailing whitespace. 
                    # If there is no body part, we default to an empty string.
                    body = parts[1].strip() if len(parts) > 1 else ""

                    return f".{title}\n[%collapsible]\n======\n{body}\n======"
                
                # We apply the restore_hook function to the content using the provided regex pattern,
                # restoring spaces in titles that were previously protected by a placeholder, and 
                # formatting them as collapsible sections in AsciiDoc, ensuring that the original formatting and 
                # spacing of the titles are preserved in the final output while also enhancing the presentation with 
                # collapsible sections for the associated content.
                content = re.sub(r.get("regex"), restore_hook, content, flags=re.S)
            else:
                # For any other restoration patterns that don't have a specific hook, 
                # we apply a standard regex substitution using the provided pattern and replacement string,
                # allowing for flexible restoration operations based on user-defined configurations, 
                # such as restoring specific formatting or syntax that may have been altered during the conversion process.
                mapping = r.get("map")
                
                if mapping:
                    # If a mapping is provided in the restoration pattern, we iterate through the key-value pairs in the mapping and 
                    # apply the regex substitution for each pair, replacing occurrences of the key in the content with 
                    # the corresponding value as defined in the replacement string, allowing for dynamic restoration based on specific mappings defined in the configuration.
                    for key, val in mapping.items():
                        content = re.sub(r.get("regex").replace("{key}", key), r.get("replacement").replace("{val}", val), content, flags=re.S)
                else:
                    # If no mapping is provided, we simply apply the regex substitution using the provided pattern and replacement string,
                    # allowing for straightforward restoration based on the defined regex and replacement in the configuration.
                    content = re.sub(r.get("regex"), r.get("replacement"), content, flags=re.S)
        
        # --- OLD IMAGE HANDLING LOGIC START (OBSOLETE) ---
        # Previous image handling logic is now obsolete and replaced by the more flexible configuration-driven approach below.
        # --- 7. IMAGE CONFIGURATION ---
        # KEEP_IMAGES_FOLDER_PREFIX = False

        # # Path Formatting
        # if KEEP_IMAGES_FOLDER_PREFIX:
        #     # Result: image::images/devices/add.png[...]
        #     content = re.sub(r'(image::?)/([^\[]+)\[', r'\1\2[', content)

        # else:
        #     # Result: image::devices/add.png[...]
        #     content = re.sub(r'(image::?)/?images/([^\[]+)\[', r'\1\2[', content)
        
        # Stripping redundant titles (where title is the same as filename)
        # content = re.sub(r'(image::?[^\[]+)\[(.*?)(?:,title="\2")\]', r'\1[\2]', content)

        # --- OLD INCLUDE HANDLING LOGIC END (OBSOLETE) ---


        # --- 7. PATH & IMAGE CONFIGURATION ---
        # Use these flags to control how file includes and images are referenced.
        # This is useful for aligning with different static site generators (like Antora).
    
        # POSSIBILITIES TABLE:
        # 1. Traversal=False, KeepPrefix=False -> image::devices/add.png[]                (Flat structure)
        # 2. Traversal=True,  KeepPrefix=False -> image::../devices/add.png[]             (Nested, no 'images' folder)
        # 3. Traversal=False, KeepPrefix=True  -> image::images/devices/add.png[]         (Standard Markdown style)
        # 4. Traversal=True,  KeepPrefix=True  -> image::../images/devices/add.png[]      (Nested with 'images' folder)
        # -------------------------------------------------------------------------------
        USE_RELATIVE_TRAVERSAL = True     # Injects '../' to move up one directory
        KEEP_IMAGES_FOLDER_PREFIX = True  # Retains the 'images/' folder in the path, common for standard AsciiDoc setups.
        # -------------------------------------------------------------------------------

        # 1. FIX INLINE SQUASHING & ESCAPING
        content = content.replace("++[]++", "[]")
        # Ensure block-level elements are separated onto new lines
        content = re.sub(r'(?i)(\.adoc\[\]|\])\s+(image::?|include::)', r'\1\n\n\2', content)

        # 2. NORMALIZE IMAGE TAGS
        # Pandoc sometimes spits out 'Image:' (single colon, capitalized).
        # \b matches the word boundary, (?=[^\s]) ensures it's attached to a path (no spaces).
        # This prevents turning conversational text like "Here is an image: " into "image:: "
        content = re.sub(r'(?i)\bimage::?(?=[^\s])', 'image::', content)

        # 3. PROCESS INCLUDES
        if USE_RELATIVE_TRAVERSAL:
            content = re.sub(r'(include::)(?!(\.\./|http))([^\[\n\s]+)', r'\1../\3', content)

        # 4. PROCESS IMAGES
        traversal = "../" if USE_RELATIVE_TRAVERSAL else ""

        if KEEP_IMAGES_FOLDER_PREFIX:
            # Result: image::../images/devices/add.png[...]
            # Strips the leading slash (if any) and injects the traversal
            content = re.sub(r'(image::)/?(?!\.\./|http)([^\[\n]+)\[', rf'\1{traversal}\2[', content)
        else:
            # Result: image::../devices/add.png[...]
            # Strips leading slash AND the 'images/' folder, then injects traversal
            content = re.sub(r'(image::)/?(?:images/)?(?!\.\./|http)([^\[\n]+)\[', rf'\1{traversal}\2[', content)

        # 5. INJECT MISSING ATTRIBUTES
        # Ensures every image gets the standard Losant rendering attributes
        def append_attrs(match) -> str:
            """
            Appends standard rendering attributes to image tags if they are missing.

            Args:
                match (re.Match): The regex match object for an image tag.

            Returns:
                str: The image tag with the standard attributes appended.
            """
            # We extract the image path and the existing attribute block from the matched image tag.
            img_path = match.group(1)
            attr_block = match.group(2)
            
            # If the attributes are already there, skip
            if "pdfwidth" in attr_block:
                return match.group(0)
                
            # Otherwise, append them cleanly
            if attr_block:
                return f"{img_path}[{attr_block},pdfwidth=100%,scalewidth=100%]"
            return f"{img_path}[pdfwidth=100%,scalewidth=100%]"

        content = re.sub(r'(image::[^\[\n]+)\[([^\]\n]*)\]', append_attrs, content)
        
        # --- 8. ANTORA XREFS ---
        def antora_xref_logic(m: re.Match) -> str:
            """
            Converts Markdown links into Antora-compatible xrefs, handling various path formats and anchors.

            Args:
                m: The regex match object for a Markdown link, containing the raw path and optional anchor
            Returns:
                str: The transformed link in Antora xref format, with the path adjusted to remove file extensions and anchors formatted correctly.
            """

            # We extract the raw path and optional anchor from the matched Markdown link. 
            # The raw path may include file extensions like .md or .adoc, which we will remove to convert it to an Antora xref format. The anchor, if present, will be formatted to ensure it is compatible with Antora's linking system.
            raw_path = m.group(1) or ""
            anchor = m.group(2) or ""

            # We process the raw path to remove any .md or .adoc extensions, as Antora xrefs should not include file extensions.
            path = raw_path.replace(".md", "").replace(".adoc", "").replace("./", "").strip("/")

            # We also check if the path contains "inputs/", which is a common pattern for Antora includes. 
            # If it does, we remove the "inputs/" prefix to convert it to a proper xref path.
            if "inputs/" in path:
                path = path.split("inputs/")[-1]
            if path:
                path = f"{path}.adoc"
            cl_anchor = ""
            if anchor:
                cl_anchor = "#" + anchor.replace("#", "").lower()
            return f"xref:{path}{cl_anchor}"

        # We apply the antora_xref_logic function to any Markdown links that match the pattern for link: or xref:, 
        # converting them into Antora-compatible xrefs by adjusting the path to remove file extensions and 
        # formatting any anchors correctly, ensuring that all internal links are properly transformed for use in Antora.
        content = re.sub(r'(?:link:|xref:)(?:\+\+)?([^\[\s#\+]+)?(#[^\[\s\+]+)?(?:\+\+)?', antora_xref_logic, content)
        content = re.sub(r'\[source,mermaid\]\n----(.*?)----', r'[mermaid]\n....\1....', content, flags=re.DOTALL)
        content = content.replace("SHIELDADMONSTARTtabs", "[tabs]\n====")
        content = content.replace("SHIELDADMONEND", "====")
        content = re.sub(r'^@tab\s+(.*)$', r'\1::', content, flags=re.M)

        # --- 9. DAPS COMPATIBILITY MODE ---
        # Set to True if building with DAPS (DocBook XML requires specific escaping and header nesting).
        # Set to False if building with Antora or standard Asciidoctor.
        DAPS_COMPATIBILITY_MODE = True

        if DAPS_COMPATIBILITY_MODE:
            # A. HEADING DEMOTION
            # DAPS/DocBook crashes if included modular files start with a Level 0 (=) Book Part header.
            # This shifts all headings down by one level (= becomes ==, == becomes ===)
            content = re.sub(r'^(={1,5})[ \t]+', r'\1= ', content, flags=re.MULTILINE)

            # B. ESCAPE HANDLEBARS
            # Escape Handlebars templates ({{ }}) so DAPS doesn't mistake them for unresolvable attributes.
            content = content.replace("{{{", "\\{\\{\\{").replace("{{", "\\{\\{")
            content = content.replace("++\\{\\{\\{++", "\\{\\{\\{").replace("++\\{\\{++", "\\{\\{")

        # --- 10. FINAL ARTIFACT CLEANUP ---
        # These are general transpiler artifacts that need to be cleaned up regardless of the build system.

        # Clean up custom admonition artifacts (.BODY and ENDADMON)
        content = re.sub(
            r'\s*\.BODY(.*?)(?:\.?ENDADMON)', 
            lambda m: f"\n====\n{m.group(1).strip()}\n====", 
            content, 
            flags=re.S
        )

        # Clean up leaked Docusaurus Admonition Shields
        content = re.sub(r'SHIELDADMONSTART([a-zA-Z]+)TITLE\s*', lambda m: f"[{m.group(1).upper()}]\n", content)

        # Restore HTML comments as AsciiDoc multi-line comment blocks (////)
        content = re.sub(
            r'HTMLCOMMENTSHIELD(.*?)HTMLCOMMENTEND', 
            lambda m: f"////\n{m.group(1).strip()}\n////\n", 
            content, 
            flags=re.DOTALL
        )

        return header_block + content.strip()
    
    
    def convert_file(self, input_path: Path, output_path: Path) -> None:
        """
        Orchestrates the conversion of a single Markdown file to AsciiDoc.
        
        Args:
            input_path (Path): Source Markdown file.
            output_path (Path): Destination for the raw AsciiDoc.
        
        Returns:
            None: Writes the converted content to output_path.
        """
        # We reset the metadata and discovered title for each file conversion to ensure that we start with a clean slate 
        # for each document, preventing any carryover of metadata or titles from previous conversions that could lead to 
        # incorrect or duplicated information in the final AsciiDoc output.
        self.metadata = {}
        self.discovered_title = None
        
        # 1. Read the raw Markdown content from the input file using UTF-8 encoding to ensure proper handling of 
        # special characters and international text.
        raw_md = input_path.read_text(encoding='utf-8')
        ready_md = self.pre_process_markdown(raw_md)
        
        # 2. We write to a temporary file so Pandoc sees the 'shielded' version
        temp_md = input_path.with_suffix('.tmp.md')
        temp_md.write_text(ready_md, encoding='utf-8')
        
        # 3. We use subprocess to call the Pandoc CLI for conversion, specifying the input format 
        # as "markdown-smart" and the output format as "asciidoc".
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
