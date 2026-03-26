"""
Location: src/transpiler_pro/core/linter.py
Description: The Style Validation Engine for Transpiler-Pro.

This module provides the `StyleLinter` class, which serves as a wrapper around 
the Vale CLI. It is responsible for:
1. Dynamic Configuration: Generating a '.vale.ini' file on-the-fly based on 
   pyproject.toml settings.
2. Vocabulary Injection: Teaching Vale new technical terms so they aren't 
   flagged as spelling errors.
3. Violation Extraction: Converting raw Vale JSON output into a format the 
   'StyleFixer' can use for automated healing.
"""

import json
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

# Import path constants for style repository location
from transpiler_pro.utils.paths import STYLES_DIR

console = Console()

class StyleLinter:
    """
    Orchestrates linguistic and style validation using Vale.

    Attributes:
        target_path (Path): The specific file (adoc/md) to be scanned.
        config_path (Path): Path to the project's pyproject.toml.
        vale_ini (Path): The path where the temporary .vale.ini will be created.
        config (Dict): Loaded configuration specific to the transpiler-pro tool.
    """

    def __init__(self, target_path: Path, config_path: Optional[Path] = None):
        """
        Initializes the linter and prepares the configuration environment.
        
        Args:
            target_path (Path): File to be validated.
            config_path (Path, optional): Path to pyproject.toml. Defaults to root.
        """
        self.target_path = target_path
        self.config_path = config_path or Path("pyproject.toml")
        
        # We generate the .vale.ini in the same directory as the config for context isolation.
        self.vale_ini: Path = self.config_path.parent / ".vale.ini"
        
        self.config = self._load_project_config()

    def _load_project_config(self) -> Dict[str, Any]:
        """Loads linter-specific settings from the [tool.transpiler-pro] section."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
        except Exception as e:
            console.print(f"[bold red]Error loading linter config:[/] {e}")
            return {}

    def setup_config(self) -> None:
        """
        Generates a temporary `.vale.ini` file required by the Vale CLI.
        
        This method performs two key tasks:
        1. Dynamic Vocab: Reads 'technical_terms' from the Knowledge Base and 
           writes them to a Vale 'accept.txt' file so they are ignored by 
           spelling checks.
        2. Config Generation: Injects style paths, alert levels, and rule-sets 
           defined in pyproject.toml into the INI format.
        """
        linter_cfg = self.config.get("linter", {})
        # Ensure paths use forward slashes for cross-platform compatibility in Vale
        styles_root = str(STYLES_DIR.resolve()).replace("\\", "/")
        
        # --- PHASE 1: DYNAMIC VOCABULARY INJECTION ---
        kb_setting = self.config.get("pipeline", {}).get("knowledge_base", "data/knowledge_base.json")
        kb_path = Path(kb_setting)
        vocab_setting = ""
        
        if kb_path.exists():
            try:
                kb_data = json.loads(kb_path.read_text(encoding="utf-8"))
                tech_terms = kb_data.get("technical_terms", [])
                
                if tech_terms:
                    # Vale expects a specific folder structure for Vocabularies
                    vocab_dir = STYLES_DIR / "vocabularies" / "Project"
                    vocab_dir.mkdir(parents=True, exist_ok=True)
                    accept_file = vocab_dir / "accept.txt"
                    
                    # Store terms in the accepted list
                    accept_file.write_text("\n".join(tech_terms), encoding="utf-8")
                    vocab_setting = "Vocab = Project"
            except Exception as e:
                console.print(f"[yellow]⚠️ Warning:[/] Vocabulary injection failed: {e}")

        # --- PHASE 2: INI CONSTRUCTION ---
        styles = linter_cfg.get("styles", ["Vale", "common", "asciidoc"])
        styles_str = ", ".join(styles)
        min_level = linter_cfg.get("min_alert_level", "suggestion")

        # Construct the Vale configuration string
        config_raw = f"""
        StylesPath = {styles_root}
        MinAlertLevel = {min_level}
        {vocab_setting}

        [*.{{adoc,md}}]
        BasedOnStyles = {styles_str}
        
        # Use the Asciidoctor parser for accurate block identification
        asciidoctor = true
        """
        
        self.vale_ini.write_text(textwrap.dedent(config_raw).strip())

    def _extract_suggestion(self, issue: Dict[str, Any]) -> str:
        """
        Extracts a viable repair suggestion from a Vale violation.
        
        Vale reports often include 'Action' parameters (e.g., the correct 
        spelling). If those aren't available, this method uses regex patterns 
        from pyproject.toml to "scrape" the suggestion out of the error message.
        """
        action_params = issue.get("Action", {}).get("Params", [])
        patterns_cfg = self.config.get("patterns", {})
        ignored = patterns_cfg.get("ignored_placeholders", [])
        
        # Priority 1: Check Vale's native suggestion parameters
        if action_params:
            candidate = str(action_params[0])
            if candidate not in ignored:
                return candidate

        # Priority 2: Scrape suggestions from the Message text using Regex
        # e.g., Message: "Use 'SUSE' instead of 'suse'" -> Extracts 'SUSE'
        search_pool = issue.get("Description", "") + " " + issue.get("Message", "")
        pattern = patterns_cfg.get("suggestion_extraction", r"['\"‘“’](.*?)['\"’]")
        
        if pattern and search_pool.strip():
            match = re.search(pattern, search_pool)
            if match:
                return match.group(1)
        
        return ""

    def run(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Executes the Vale CLI and returns a structured map of findings.
        
        Returns:
            Dict: Key is file path, Value is a list of violation dictionaries 
                  containing Line, Check ID, Severity, and Suggestion.
        """
        try:
            abs_target = str(self.target_path.resolve())
            
            # Execute Vale in JSON mode for programmatic parsing
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

            # Convert raw Vale schema to Transpiler-Pro's internal repair schema
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

        except (FileNotFoundError, json.JSONDecodeError, subprocess.SubprocessError) as e:
            console.print(f"[bold red]Linter Execution Error:[/] {e}")
            return {}

    def display_report(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Renders a user-friendly report of the findings.
        The actual visual table is commented out to allow CLI orchestration 
        to handle final output density, but the logic remains for debugging.
        """
        if not data or not any(data.values()):
            console.print("\n✨ [bold green]Quality Check Passed: Document meets all style guide requirements.[/]")
            return

        # Table rendering code...
        # Theme-based coloring for different alert levels
        # linter_cfg = self.config.get("linter", {})
        # theme = linter_cfg.get("theme", {"error": "red", "warning": "yellow", "suggestion": "blue"})
        # table = Table(title="Style Guide Validation Report", title_style="bold cyan")
        # table.add_column("Line", style="magenta", justify="right")
        # table.add_column("Severity", style="bold")
        # table.add_column("Message", style="white")
        # table.add_column("Rule ID", style="yellow")

        # for _, issues in data.items():
        #     for issue in issues:
        #         sev = issue['Severity']
        #         color = theme.get(sev.lower(), "white")
                
        #         table.add_row(
        #             str(issue['Line']),
        #             f"[{color}]{sev}[/]",
        #             issue['Message'],
        #             issue['Check']
        #         )

        # console.print(table)