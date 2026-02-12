"""Location: src/transpiler_pro/core/refiner.py
Description: The navigation structure generator for Personal Transpiler-Pro.
Parses JavaScript sidebar configurations and transforms them into 
Antora-compliant 'nav.adoc' files using hierarchical cross-references.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Union


class SidebarNavigator:
    """Translates dynamic JavaScript sidebar definitions into static AsciiDoc navigation.
    
    This engine extracts JSON metadata from JS source files, flattens the 
    category hierarchy, and maps file identifiers to Antora xrefs.
    """

    def convert_js_to_adoc(self, js_path: Path, adoc_path: Path) -> None:
        """Processes a sidebars.js file and writes the resulting navigation to AsciiDoc.
        
        Args:
            js_path (Path): Path to the source sidebars.js file.
            adoc_path (Path): Path where the final nav.adoc should be generated.
        """
        if not js_path.exists():
            return

        content = js_path.read_text(encoding='utf-8')
        
        # Extract the object assignment from the JS file using regex
        # Specifically targets 'const sidebars = { ... };'
        json_match = re.search(r'const sidebars = (\{.*\})', content, re.S)
        if not json_match:
            return
        
        # Normalization: Convert JavaScript object literal syntax to strict JSON
        # 1. Quote unquoted keys (e.g., label: -> "label":)
        json_str = re.sub(r'(\w+):', r'"\1":', json_match.group(1))
        # 2. Convert single quotes to double quotes and remove newlines for parsing
        json_str = json_str.replace("'", '"').replace('\n', '')
        
        try:
            data: Dict[str, Any] = json.loads(json_str)
            nav_lines: List[str] = []

            # Iterate through the top-level sidebar sections
            for _, items in data.items():
                nav_lines.extend(self._parse_sidebar_items(items))
                
            adoc_path.write_text("\n".join(nav_lines), encoding='utf-8')
            
        except json.JSONDecodeError:
            # Silence errors for invalid JSON formats, maintaining pipeline stability
            pass

    def _parse_sidebar_items(self, items: List[Union[str, Dict]], depth: int = 1) -> List[str]:
        """Recursively parses sidebar items to build a nested AsciiDoc list.
        
        Args:
            items (List[Union[str, Dict]]): A list of document IDs or 
                category dictionaries.
            depth (int): Current nesting level (mapped to '*' counts).
            
        Returns:
            List[str]: A list of formatted AsciiDoc navigation lines using 
                Antora's tiered bullet syntax.
        """
        lines: List[str] = []
        # Antora uses '*' for hierarchy levels (e.g., *, **, ***)
        prefix = '*' * depth
        
        for item in items:
            # Case 1: Simple string item (direct file reference)
            if isinstance(item, str):
                # Format: "path/to-file" -> "To File"
                label = item.split('/')[-1].replace('-', ' ').title()
                lines.append(f"{prefix} xref:{item}.adoc[{label}]")
                
            # Case 2: Dictionary item (Category or Link with ID)
            elif isinstance(item, dict):
                label = item.get('label', 'Category')
                
                # Check if the category itself has a landing page
                if 'link' in item and isinstance(item['link'], dict):
                    link_id = item['link'].get('id', '')
                    lines.append(f"{prefix} xref:{link_id}.adoc[{label}]")
                else:
                    # Category header without a direct link
                    lines.append(f"{prefix} {label}")
                
                # Recursively parse nested children
                if 'items' in item:
                    lines.extend(self._parse_sidebar_items(item['items'], depth + 1))
                    
        return lines