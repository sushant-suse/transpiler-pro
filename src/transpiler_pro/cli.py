"""Location: src/transpiler_pro/cli.py
Description: Command-line interface for Personal Transpiler-Pro.
Provides a unified entry point to execute the conversion and linting pipeline 
using the Typer framework for robust argument parsing.
"""

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

# Internal module imports
from transpiler_pro.core.converter import DocConverter
from transpiler_pro.core.linter import StyleLinter
from transpiler_pro.utils.paths import INPUT_DIR, OUTPUT_DIR

# 1. Initialize the CLI Application
# We use Typer to create a professional sub-command structure
app = typer.Typer(
    name="Personal Transpiler-Pro",
    help="Professional Documentation Pipeline: Convert Markdown to Antora and validate style."
)
console = Console()

@app.callback()
def callback() -> None:
    """Automated pipeline for converting high-complexity Markdown into
    SUSE-standard AsciiDoc.
    """
    pass

@app.command(name="run")
def execute_pipeline(
    file_name: Optional[str] = typer.Option(
        None, 
        "--file", "-f", 
        help="Target a specific file within the data/inputs directory"
    ),
    lint_only: bool = typer.Option(
        False, 
        "--lint-only", 
        help="Bypass the conversion phase and run the style linter on existing output"
    )
) -> None:
    """Executes the comprehensive transpilation and linting workflow."""
    # Initialize the conversion engine
    converter = DocConverter()
    
    # Logic: Target a specific file or batch process the entire input directory
    if file_name:
        target_files: List[Path] = [INPUT_DIR / file_name]
    else:
        # Support both standard Markdown and MDX extensions
        target_files = list(INPUT_DIR.glob("*.md")) + list(INPUT_DIR.glob("*.mdx"))

    # Early exit if no valid targets are found
    if not target_files or not any(f.exists() for f in target_files):
        console.print("[bold yellow]Notification:[/] No source files detected in 'data/inputs/'.")
        return

    for md_path in target_files:
        # Define the output destination in the data/outputs folder
        adoc_path = OUTPUT_DIR / md_path.with_suffix(".adoc").name
        
        # Phase 1: Structural Transformation
        if not lint_only:
            console.print(f"\n[bold blue]Phase 1:[/] Transforming [cyan]{md_path.name}[/]")
            try:
                converter.convert_file(md_path, adoc_path)
                console.print("  [bold green]✓[/] Structural conversion finalized.")
            except Exception as error:
                console.print(f"  [bold red]✗[/] Pipeline Interrupted: {error}")
                continue
        
        # Phase 2: Linguistic Validation (Style Linting)
        console.print(f"[bold blue]Phase 2:[/] Validating [cyan]{adoc_path.name}[/] style standards")
        
        linter = StyleLinter(adoc_path)
        linter.setup_config()
        
        findings = linter.run()
        linter.display_report(findings)

def main() -> None:
    """Entry point for the console script."""
    app()

if __name__ == "__main__":
    main()
