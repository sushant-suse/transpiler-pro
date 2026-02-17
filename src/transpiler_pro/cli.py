"""Location: src/transpiler_pro/cli.py
Description: Orchestration Layer for Personal Transpiler-Pro.
Passes configuration context to core engines to eliminate hardcoded fallbacks.
"""

import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console

from transpiler_pro.core.converter import DocConverter
from transpiler_pro.core.fixer import StyleFixer
from transpiler_pro.core.linter import StyleLinter
from transpiler_pro.utils.paths import INPUT_DIR, OUTPUT_DIR

app = typer.Typer(
    name="Personal Transpiler-Pro",
    help="Enterprise Documentation Pipeline: Adaptive MD-to-ADOC conversion."
)
console = Console()

# Define the central config path as a single source of truth
DEFAULT_CONFIG = Path("pyproject.toml")

def load_config(config_path: Path) -> Dict[str, Any]:
    """Helper to load global pipeline settings from a specific path."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    except Exception:
        return {}

@app.command(name="run")
def execute_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file"),
    lint_only: bool = typer.Option(False, "--lint-only", help="Run linter only"),
    fix: bool = typer.Option(False, "--fix", help="Auto-repair style violations"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Path to pyproject.toml")
) -> None:
    """Executes the conversion, linting, and Auto-Heal workflow using dynamic config."""
    
    # 1. Load configuration and inject into engines
    pipeline_config = load_config(config)
    
    # DYNAMIC INJECTION: Engines receive the config path so they never use hardcoded fallbacks
    converter = DocConverter(config_path=config)
    fixer = StyleFixer(config_path=config)
    
    # 2. Target Detection
    if file_name:
        target_files = [INPUT_DIR / file_name]
    else:
        # Get extensions from config, with a very thin fallback if config is empty
        exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])
        target_files = [p for p in INPUT_DIR.iterdir() if p.suffix in exts]

    if not target_files:
        console.print("[bold yellow]Notification:[/] No source files detected in inputs directory.")
        return

    # 3. Pipeline Execution Loop
    for md_path in target_files:
        if not md_path.exists():
            continue
            
        adoc_path = OUTPUT_DIR / md_path.with_suffix(".adoc").name
        
        # --- Phase 1: Structural Transformation ---
        if not lint_only:
            console.print(f"\n[bold blue]Phase 1:[/] Transforming [cyan]{md_path.name}[/]")
            try:
                converter.convert_file(md_path, adoc_path)
            except Exception as e:
                console.print(f"  [bold red]Error during conversion:[/] {e}")
                continue
        
        # --- Phase 2: Linguistic Validation ---
        if adoc_path.exists():
            console.print(f"[bold blue]Phase 2:[/] Validating [cyan]{adoc_path.name}[/] style standards")
            # Inject config path into Linter
            linter = StyleLinter(adoc_path, config_path=config)
            linter.setup_config()
            findings = linter.run()
            linter.display_report(findings)

            # --- Phase 3: Automated Repair ---
            if fix and findings:
                console.print(f"[bold blue]Phase 3:[/] Applying 'Auto-Heal' to [cyan]{adoc_path.name}[/]")
                file_key = str(adoc_path.resolve())
                file_violations = findings.get(file_key, [])
                
                if file_violations:
                    repaired_count = fixer.fix_file(adoc_path, file_violations)
                    if repaired_count > 0:
                        console.print(f"  [bold green]✨ Success:[/] Repaired {repaired_count} violations.")
                        linter.display_report(linter.run())

@app.command(name="refine")
def bulk_refine(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c")
) -> None:
    """Applies global Antora headers from config to all converted outputs."""
    pipeline_config = load_config(config)
    antora_cfg = pipeline_config.get("antora", {})
    
    # Dynamic headers from config
    headers = antora_cfg.get("headers", [])
    if not headers:
        return

    header_block = "\n".join(headers) + "\n\n"
    console.print("[bold blue]Phase 4:[/] Injecting Antora headers into output files...")
    
    refined_count = 0
    for adoc_path in OUTPUT_DIR.glob("*.adoc"):
        content = adoc_path.read_text(encoding="utf-8")
        if not content.startswith(headers[0]):
            adoc_path.write_text(header_block + content, encoding="utf-8")
            console.print(f"  [bold green]✓[/] Refined: [white]{adoc_path.name}[/]")
            refined_count += 1
            
    if refined_count == 0:
        console.print("  [dim]No new files required refinement.[/]")

def main() -> None:
    app()

if __name__ == "__main__":
    main()