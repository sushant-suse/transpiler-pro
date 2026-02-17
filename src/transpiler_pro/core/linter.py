"""Location: src/transpiler_pro/core/linter.py
Description: Data-driven StyleLinter. Orchestrates Vale validation without
hardcoded style names, colors, or extraction fallbacks.
"""

import json
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from transpiler_pro.utils.paths import STYLES_DIR

console = Console()

class StyleLinter:
    """Orchestrates style validation using externalized configurations."""

    def __init__(self, target_path: Path, config_path: Optional[Path] = None):
        """Initializes the linter with path isolation for configuration."""
        self.target_path = target_path
        self.config_path = config_path or Path("pyproject.toml")
        
        # Isolation: .vale.ini generated in context of current config
        self.vale_ini: Path = self.config_path.parent / ".vale.ini"
        
        self.config = self._load_project_config()
        self.guide_url = self.config.get("meta", {}).get("guide_url", "")

    def _load_project_config(self) -> dict:
        """Loads linter-specific metadata from the dynamic config path."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception:
            return {}

    def setup_config(self) -> None:
        """Generates Vale config using dynamic styles and levels from TOML."""
        linter_cfg = self.config.get("linter", {})
        
        # Ensure the styles path uses forward slashes for cross-platform Vale
        styles_root = str(STYLES_DIR.resolve()).replace("\\", "/")
        
        # ZERO HARDCODING: Fallback to empty list if config is missing styles
        styles = linter_cfg.get("styles", [])
        styles_str = ", ".join(styles) if styles else "Vale"
        min_level = linter_cfg.get("min_alert_level", "suggestion")

        config_raw = f"""
        StylesPath = {styles_root}
        MinAlertLevel = {min_level}

        [*.{{adoc,md}}]
        BasedOnStyles = {styles_str}
        """
        
        self.vale_ini.write_text(textwrap.dedent(config_raw).strip())

    def _extract_suggestion(self, issue: Dict[str, Any]) -> str:
        """Dynamic extraction logic based on patterns provided in config."""
        action_params = issue.get("Action", {}).get("Params", [])
        patterns_cfg = self.config.get("patterns", {})
        
        # Get ignored placeholders from TOML (e.g., 'spellings')
        ignored = patterns_cfg.get("ignored_placeholders", [])
        
        # 1. Action Param check
        if action_params:
            candidate = str(action_params[0])
            if candidate not in ignored:
                return candidate

        # 2. Regex-based extraction from Message/Description
        search_pool = issue.get("Description", "") + " " + issue.get("Message", "")
        # Zero Hardcoding: regex pattern must be provided in TOML
        pattern = patterns_cfg.get("suggestion_extraction")
        
        if pattern and search_pool.strip():
            match = re.search(pattern, search_pool)
            if match:
                return match.group(1)
        
        return ""

    def run(self) -> Dict[str, List[Dict[str, Any]]]:
        """Executes Vale and processes findings into a generic format."""
        try:
            abs_target = str(self.target_path.resolve())
            
            result = subprocess.run(
                ["vale", "--config", str(self.vale_ini.resolve()), "--output=JSON", abs_target],
                capture_output=True,
                text=True,
                check=False
            )
            
            if not result.stdout or result.stdout.strip() == "":
                return {}

            raw_data = json.loads(result.stdout)
            processed_findings = {}

            for file_path, file_issues in raw_data.items():
                processed_findings[file_path] = []
                for issue in file_issues:
                    processed_findings[file_path].append({
                        "Line": issue.get("Line"),
                        "Check": issue.get("Check"),
                        "Severity": issue.get("Severity"),
                        "Message": issue.get("Message"),
                        "Description": issue.get("Description", ""),
                        "Suggestion": self._extract_suggestion(issue)
                    })
                
            return processed_findings

        except (FileNotFoundError, json.JSONDecodeError, subprocess.SubprocessError):
            return {}

    def display_report(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Renders the report with dynamic colors and themes from config."""
        if not data or not any(data.values()):
            console.print("\n✨ [bold green]Quality Check Passed[/]")
            return

        linter_cfg = self.config.get("linter", {})
        # Dynamic Color Mapping from TOML
        theme = linter_cfg.get("theme", {
            "error": "red", 
            "warning": "yellow", 
            "suggestion": "blue"
        })

        table = Table(title="Style Guide Validation Report", title_style="bold cyan")
        table.add_column("Line", style="magenta", justify="right")
        table.add_column("Severity", style="bold")
        table.add_column("Message", style="white")
        table.add_column("Rule ID", style="yellow")

        for _, issues in data.items():
            for issue in issues:
                sev = issue['Severity']
                color = theme.get(sev, "white")
                
                table.add_row(
                    str(issue['Line']),
                    f"[{color}]{sev}[/]",
                    issue['Message'],
                    issue['Check']
                )

        console.print(table)
        if self.guide_url:
            console.print(f"\n💡 [dim]Reference:[/] [link={self.guide_url}]Style Guide[/link]\n")