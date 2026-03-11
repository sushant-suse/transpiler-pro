"""
Location: src/transpiler_pro/cli.py

Description: Orchestration Layer for Transpiler-Pro.
Coordinates:
1. X-Command: Markdown to Raw AsciiDoc (Intermediate).
2. Y-Command: Style Validation and Auto-Repair (Final Output).
"""

import tomllib
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console

from transpiler_pro.core.converter import DocConverter
from transpiler_pro.core.fixer import StyleFixer
from transpiler_pro.core.linter import StyleLinter
from transpiler_pro.utils.paths import INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR

app = typer.Typer(
    name="transpiler-pro",
    help="Enterprise Documentation Pipeline with X (Convert) and Y (Repair) commands.",
    no_args_is_help=True, 
    add_completion=False
)
console = Console()

DEFAULT_CONFIG = Path("pyproject.toml")

def load_config(config_path: Path) -> Dict[str, Any]:
    """Loads global pipeline settings from a TOML configuration file."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    except Exception:
        return {}

def sync_styles() -> None:
    """Synchronizes the SUSE Style Guide submodule via Git."""
    console.print("\n[bold blue]Pre-flight:[/] Syncing SUSE Style Guide via Git...")
    try:
        subprocess.run(
            ["git", "submodule", "update", "--init", "--remote", "styles/suse-styles"],
            check=True, capture_output=True, text=True
        )
        console.print("  [bold green]✓[/] Style guide is synchronized.")
    except Exception:
        console.print("  [bold yellow]⚠️ Warning:[/] Sync failed. Using local cached styles.")

@app.command(name="x-convert")
def convert_x(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific MD file"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    COMMAND X: Converts Markdown files to raw AsciiDoc in the intermediate directory.
    """
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    converter = DocConverter(config_path=config_path)

    if file_name:
        target_files = [INPUT_DIR / file_name]
    else:
        exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])
        target_files = [p for p in INPUT_DIR.iterdir() if p.suffix in exts]

    for md_path in target_files:
        if not md_path.exists(): 
            continue
        # Output goes to INTERMEDIATE_DIR
        inter_path = INTERMEDIATE_DIR / md_path.with_suffix(".adoc").name
        console.print(f"[bold blue]X-Phase:[/] Converting [cyan]{md_path.name}[/] -> [yellow]{inter_path.name}[/]")
        converter.convert_file(md_path, inter_path)

@app.command(name="y-repair")
def repair_y(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific ADOC file in intermediate"),
    fix: bool = typer.Option(True, "--fix/--no-fix", help="Apply auto-repairs"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    COMMAND Y: Validates and repairs AsciiDoc files from the intermediate directory.
    """
    config_path = Path(config)
    fixer = StyleFixer(config_path=config_path)

    if file_name:
        target_files = [INTERMEDIATE_DIR / file_name]
    else:
        target_files = list(INTERMEDIATE_DIR.glob("*.adoc"))

    for inter_path in target_files:
        if not inter_path.exists(): 
            continue
        
        # Move to final OUTPUT_DIR for processing
        final_path = OUTPUT_DIR / inter_path.name
        shutil.copy(inter_path, final_path)
        
        console.print(f"\n[bold blue]Y-Phase:[/] Validating [cyan]{final_path.name}[/]")
        linter = StyleLinter(final_path, config_path=config_path)
        linter.setup_config()
        findings = linter.run()
        linter.display_report(findings)

        if fix and findings:
            file_key = str(final_path.resolve())
            file_violations = findings.get(file_key, [])
            if file_violations:
                repaired_count = fixer.fix_file(final_path, file_violations)
                console.print(f"  [bold green]✨ Repaired {repaired_count} violations in {final_path.name}.[/]")
                # Final check
                linter.display_report(linter.run())

@app.command(name="run")
def execute_full_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f"),
    fix: bool = typer.Option(True, "--fix"),
    sync: bool = typer.Option(False, "--sync"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    FULL PIPELINE: Executes both Command X and Command Y sequentially.
    """
    if sync:
        sync_styles()
    
    # Run X
    convert_x(file_name=file_name, config=config)
    # Run Y
    repair_y(file_name=file_name, fix=fix, config=config)

@app.command(name="version")
def version():
    """Display the version of Transpiler-Pro."""
    console.print("Transpiler-Pro v1.0.0")

def main():
    app()

if __name__ == "__main__":
    main()