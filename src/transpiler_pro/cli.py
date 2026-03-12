"""
Location: src/transpiler_pro/cli.py
Description: Orchestration Layer for Transpiler-Pro with Git Sync and Full Pipeline execution.
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
from transpiler_pro.core.repair import LinguisticEngine
from transpiler_pro.utils.logger import AuditLogger
from transpiler_pro.utils.paths import INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR, STYLES_DIR

app = typer.Typer(
    name="transpiler-pro",
    help="Enterprise Documentation Pipeline with X (Convert) and Y (Repair) commands.",
    no_args_is_help=True, 
    add_completion=False
)
console = Console()

DEFAULT_CONFIG = Path("pyproject.toml")

def load_config(config_path: Path) -> Dict[str, Any]:
    """Loads global pipeline settings."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    except Exception:
        return {}

@app.command(name="sync")
def sync_styles(config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")) -> None:
    """Synchronizes the SUSE Style Guide repository via Git."""
    pipeline_config = load_config(Path(config))
    repo_url = pipeline_config.get("pipeline", {}).get(
        "official_style_guide", 
        "https://github.com/openSUSE/suse-vale-styleguide.git"
    )
    target_dir = STYLES_DIR / "suse-styles"

    console.print(f"\n[bold blue]Sync:[/] Updating Style Guide from [cyan]{repo_url}[/]")
    
    try:
        if not target_dir.exists():
            console.print("  [yellow]➜[/] Cloning fresh repository...")
            subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True, capture_output=True)
        else:
            console.print("  [yellow]➜[/] Pulling latest changes...")
            subprocess.run(["git", "-C", str(target_dir), "pull"], check=True, capture_output=True)
        console.print("  [bold green]✓[/] Style guide is up to date.")
    except Exception as e:
        console.print(f"  [bold yellow]⚠️ Warning:[/] Sync failed. Using local cache. Error: {e}")

@app.command(name="x-convert")
def convert_x(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific MD file"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """COMMAND X: Converts Markdown files to raw AsciiDoc."""
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
        inter_path = INTERMEDIATE_DIR / md_path.with_suffix(".adoc").name
        console.print(f"[bold blue]X-Phase:[/] Converting [cyan]{md_path.name}[/] -> [yellow]{inter_path.name}[/]")
        converter.convert_file(md_path, inter_path)

@app.command(name="y-repair")
def repair_y(
    file_name: Optional[str] = typer.Option(None, "--file", "-f"),
    fix: bool = typer.Option(True, "--fix/--no-fix"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """COMMAND Y: Validates and repairs AsciiDoc files."""
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    
    repair_engine = LinguisticEngine(knowledge_base=pipeline_config)
    audit_logger = AuditLogger()
    fixer = StyleFixer(config_path=config_path)

    target_files = [INTERMEDIATE_DIR / file_name] if file_name else list(INTERMEDIATE_DIR.glob("*.adoc"))

    for inter_path in target_files:
        if not inter_path.exists(): 
            continue
        
        final_path = OUTPUT_DIR / inter_path.name
        shutil.copy(inter_path, final_path)
        console.print(f"\n[bold blue]Y-Phase:[/] Validating [cyan]{final_path.name}[/]")
        
        linter = StyleLinter(final_path, config_path=config_path)
        linter.setup_config()
        
        initial_findings = linter.run()
        linter.display_report(initial_findings)
        
        if fix and initial_findings:
            # 1. Healing
            content = final_path.read_text(encoding="utf-8")
            healed = repair_engine.repair_text(content)
            final_path.write_text(healed, encoding="utf-8")
            
            file_key = str(final_path.resolve())
            fixer.fix_file(final_path, initial_findings.get(file_key, []))

            # 2. Re-scan & Reporting
            console.print(f"  [bold green]✨ Processing complete for {final_path.name}.[/]")
            final_findings = linter.run()
            linter.display_report(final_findings)
            
            # CALCULATE DYNAMIC SUMMARY
            initial_count = len(initial_findings.get(file_key, []))
            residual_violations = final_findings.get(file_key, [])
            residual_count = len(residual_violations)
            fixed_count = initial_count - residual_count
            
            for v in residual_violations:
                audit_logger.log_issue(
                    file_path=str(final_path),
                    line=v.get("Line") or 1,
                    severity=v.get("Severity") or "warning",
                    message=v.get("Message") or "Review style",
                    rule_id=v.get("Check") or "Style.General"
                )
            
            if residual_count > 0:
                console.print(f"  [bold green]{fixed_count} fixed.[/] [bold yellow]📋 {residual_count} items require manual attention. See logs.[/]")
            else:
                console.print(f"  [bold green]✅ {fixed_count} fixed. Document is style-guide perfect![/]")

@app.command(name="full-run")
def execute_full_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Pull latest styles before running"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """THE COMBO COMMAND: Performs Sync, Command X, and Command Y sequentially."""
    if sync:
        sync_styles(config=config)
    
    # Run Conversion
    convert_x(file_name=file_name, config=config)
    
    # Run Repair (If file_name was test.md, Command Y needs test.adoc)
    adoc_file = Path(file_name).with_suffix(".adoc").name if file_name else None
    repair_y(file_name=adoc_file, fix=True, config=config)

def main():
    app()

if __name__ == "__main__":
    main()