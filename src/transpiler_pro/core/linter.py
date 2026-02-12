"""Location: src/transpiler_pro/core/linter.py
Description: The automated style validation engine for Personal Transpiler-Pro.
Integrates the Vale CLI with custom SUSE-standard rulesets to perform 
heuristic analysis on converted AsciiDoc content.
"""

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from transpiler_pro.utils.paths import BASE_DIR, STYLES_DIR

console = Console()

class StyleLinter:
    """Orchestrates the style validation phase using the Vale linting engine.
    
    This class manages the lifecycle of the linter configuration, executes 
    rule-based checks against converted documents, and generates visual reports.
    """

    def __init__(self, target_path: Path):
        """Initializes the linter for a specific document.
        
        Args:
            target_path (Path): Path to the .adoc or .md file to be validated.
        """
        self.target_path = target_path
        self.vale_ini: Path = BASE_DIR / ".vale.ini"
        self.guide_url: str = "https://documentation.suse.com/style/current/html/style-guide-adoc/index.html"

    def setup_config(self) -> None:
        """Dynamically generates a Vale configuration file (.vale.ini) tailored
        to the project's style requirements and local paths.
        """
        styles_root = STYLES_DIR 
        
        # Maintenance: Remove conflicting default spelling rules to prioritize 
        # the specialized SUSE dictionary.
        spelling_file = styles_root / "common" / "Spelling.yml"
        if spelling_file.exists():
            spelling_file.unlink()

        # Define the linting environment
        # 'config', 'common', and 'asciidoc' refer to the SUSE-specific YAML rulesets.
        config_raw = f"""
        StylesPath = {styles_root}
        MinAlertLevel = suggestion

        [*.{{adoc,md}}]
        BasedOnStyles = Vale, config, common, asciidoc
        """
        
        self.vale_ini.write_text(textwrap.dedent(config_raw).strip())

    def run(self) -> Dict[str, List[Dict[str, Any]]]:
        """Executes the Vale CLI against the target document and parses the result.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A structured dictionary where keys 
                are file paths and values are lists of issue dictionaries 
                containing 'Line', 'Severity', 'Message', and 'Check'.
        """
        try:
            # Resolve absolute path to ensure Vale identifies the file correctly
            abs_target = self.target_path.resolve()
            
            # Execute Vale with JSON output format for programmatic parsing
            result = subprocess.run(
                ["vale", "--config", str(self.vale_ini), "--output=JSON", str(abs_target)],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.stderr:
                console.print(f"[yellow]Vale Execution Warning:[/] {result.stderr}")
                
            return json.loads(result.stdout) if result.stdout else {}

        except FileNotFoundError:
            console.print("[bold red]Critical Error:[/] Vale CLI is not installed or not in PATH.")
            return {}
        except json.JSONDecodeError:
            console.print("[bold red]Analysis Error:[/] Could not interpret Vale JSON output.")
            return {}

    def display_report(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Parses raw linting data and renders a formatted table in the terminal.

        Args:
            data (Dict[str, List[Dict[str, Any]]]): The JSON findings returned from 
                the run() method, containing lists of style violations.
        """
        # Early exit if no issues are detected
        if not data or not any(data.values()):
            console.print("\n✨ [bold green]Quality Check Passed:[/] No style violations detected.")
            return

        table = Table(title="Style Guide Validation Report", title_style="bold cyan")
        table.add_column("Line", style="magenta", justify="right")
        table.add_column("Severity", style="bold")
        table.add_column("Message", style="white")
        table.add_column("Rule ID", style="yellow")

        # Iterate through findings for the specific file
        for _, issues in data.items():
            for issue in issues:
                severity = issue['Severity']
                
                # Assign semantic colors based on violation level
                color = {
                    "error": "red",
                    "warning": "yellow",
                    "suggestion": "blue"
                }.get(severity, "white")
                
                table.add_row(
                    str(issue['Line']),
                    f"[{color}]{severity}[/]",
                    issue['Message'],
                    issue['Check']
                )

        console.print(table)
        console.print(f"\n💡 [dim]Reference:[/] [link={self.guide_url}]Official SUSE Style Guide[/link]\n")