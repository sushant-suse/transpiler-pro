"""
Location: src/transpiler_pro/cli.py

Description: Orchestration Layer for Transpiler-Pro.

This module serves as the primary entry point for the documentation pipeline.

It coordinates:

1. **Sync**: Updating SUSE Style Guides via Git.
2. **Conversion**: Transforming Markdown to AsciiDoc.
3. **Linting**: Detecting style violations via Vale.
4. **Fixing**: Applying NLP-based auto-repairs.
"""

import tomllib
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console

from transpiler_pro.core.converter import DocConverter
from transpiler_pro.core.fixer import StyleFixer
from transpiler_pro.core.linter import StyleLinter
from transpiler_pro.utils.paths import INPUT_DIR, OUTPUT_DIR

app = typer.Typer(
    name="transpiler-pro",
    help="Enterprise Documentation Pipeline with Autonomous Style Sync.",
    no_args_is_help=True, 
    add_completion=False
)
console = Console()

DEFAULT_CONFIG = Path("pyproject.toml")

def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Loads global pipeline settings from a TOML configuration file.
    
    Args:
        config_path: Path to the `pyproject.toml` file.
        
    Returns:
        A dictionary containing the `tool.transpiler-pro` configuration block.
    """
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    except Exception:
        return {}

def sync_styles() -> None:
    """
    Synchronizes the SUSE Style Guide submodule with the remote repository.
    
    This ensures that the latest enterprise linguistic standards are applied 
    before the linting phase begins.
    """
    console.print("\n[bold blue]Pre-flight:[/] Syncing SUSE Style Guide via Git...")
    try:
        subprocess.run(
            ["git", "submodule", "update", "--init", "--remote", "styles/suse-styles"],
            check=True, 
            capture_output=True,
            text=True
        )
        console.print("  [bold green]✓[/] Style guide is synchronized and up-to-date.")
    except subprocess.CalledProcessError as e:
        console.print(f"  [bold yellow]⚠️ Warning:[/] Sync failed. Using local cached styles. {e.stderr}")
    except FileNotFoundError:
        console.print("  [bold red]Error:[/] Git not found in system path. Skipping sync.")

def run_pipeline(
    file_name: Optional[str] = None,
    lint_only: bool = False,
    fix: bool = False,
    sync: bool = False,
    config_path: Path = DEFAULT_CONFIG
) -> None:
    """
    The decoupled logic for the transformation and validation pipeline.
    
    This function allows for direct invocation without CLI-specific 
    argument validation, facilitating more robust testing.
    """
    # 0. Optional Style Sync
    if sync:
        sync_styles()

    # 1. Load configuration and inject into engines
    pipeline_config = load_config(config_path)
    converter = DocConverter(config_path=config_path)
    fixer = StyleFixer(config_path=config_path)
    
    # 2. Target Detection
    if file_name:
        target_files = [INPUT_DIR / file_name]
    else:
        exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])
        if not INPUT_DIR.exists():
            console.print(f"[bold yellow]Notification:[/] Directory {INPUT_DIR} not found.")
            return
        target_files = [p for p in INPUT_DIR.iterdir() if p.suffix in exts]

    if not target_files:
        console.print("[bold yellow]Notification:[/] No source files detected.")
        return

    # 3. Pipeline Execution Loop
    for md_path in target_files:
        if not md_path.exists(): 
            continue
            
        adoc_path = OUTPUT_DIR / md_path.with_suffix(".adoc").name
        
        # Phase 1: Conversion
        if not lint_only:
            console.print(f"\n[bold blue]Phase 1:[/] Converting [cyan]{md_path.name}[/]")
            try:
                converter.convert_file(md_path, adoc_path)
            except Exception as e:
                console.print(f"  [bold red]Error:[/] {e}")
                continue
        
        # Phase 2 & 3: Linter & Fixer
        if adoc_path.exists():
            console.print(f"[bold blue]Phase 2:[/] Validating [cyan]{adoc_path.name}[/]")
            linter = StyleLinter(adoc_path, config_path=config_path)
            linter.setup_config()
            findings = linter.run()
            linter.display_report(findings)

            if fix and findings:
                console.print(f"[bold blue]Phase 3:[/] Auto-repairing [cyan]{adoc_path.name}[/]")
                file_key = str(adoc_path.resolve())
                file_violations = findings.get(file_key, [])
                
                if file_violations:
                    repaired_count = fixer.fix_file(adoc_path, file_violations)
                    if repaired_count > 0:
                        console.print(f"  [bold green]✨ Repaired {repaired_count} violations.[/]")
                        linter.display_report(linter.run())

@app.command(name="run")
def execute_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file"),
    lint_only: bool = typer.Option(False, "--lint-only", help="Run linter only"),
    fix: bool = typer.Option(False, "--fix", help="Auto-repair style violations"),
    sync: bool = typer.Option(False, "--sync", help="Sync style guide before execution"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c", help="Path to config file")
) -> None:
    """
    Executes the main conversion, validation, and auto-heal workflow.
    """
    run_pipeline(
        file_name=file_name,
        lint_only=lint_only,
        fix=fix,
        sync=sync,
        config_path=Path(config)
    )

@app.command(name="version")
def version():
    """Display the version of Transpiler-Pro."""
    console.print("Transpiler-Pro v1.0.0")

def main():
    """Main entry point."""
    app()

if __name__ == "__main__":
    main()