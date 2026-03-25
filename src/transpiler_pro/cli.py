"""
Location: src/transpiler_pro/cli.py
Description: Orchestration Layer for Transpiler-Pro.
Fixed: Dangerous 'reset --hard' removed from sync; Recursion logic fixed for subfolders.
"""

import tomllib
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, List

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
    """
    Synchronizes the SUSE Style Guide repository safely.
    Removed 'reset --hard' to prevent accidental deletion of user code.
    """
    pipeline_config = load_config(Path(config))
    repo_url = pipeline_config.get("pipeline", {}).get(
        "official_style_guide", 
        "https://github.com/openSUSE/suse-vale-styleguide.git"
    )
    target_dir = STYLES_DIR 

    console.print(f"\n[bold blue]Sync:[/] Updating Style Guide from [cyan]{repo_url}[/]")
    
    try:
        if not target_dir.exists():
            console.print("  [yellow]➜[/] Cloning fresh repository...")
            subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True, capture_output=True)
        else:
            console.print("  [yellow]➜[/] Pulling latest changes safely...")
            # We use pull without reset. This only updates the styles/ folder content.
            subprocess.run(["git", "-C", str(target_dir), "pull", "origin", "master"], check=True, capture_output=True)
            
        console.print("  [bold green]✓[/] Style guide updated.")
    except Exception as e:
        console.print(f"  [bold yellow]⚠️ Warning:[/] Sync skipped. Using local cache. Error: {e}")

@app.command(name="x-convert")
def convert_x(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific MD file"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """COMMAND X: Converts Markdown files to raw AsciiDoc with recursive directory mirroring."""
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    converter = DocConverter(config_path=config_path)

    target_files: List[Path] = []
    exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])

    if file_name:
        path_obj = Path(file_name)
        input_file = path_obj if path_obj.is_absolute() else INPUT_DIR / file_name
        if input_file.exists():
            target_files = [input_file]
    else:
        # RECURSIVE FIX: Find all files matching extensions across all subfolders
        for ext in exts:
            target_files.extend(list(INPUT_DIR.rglob(f"*{ext}")))

    if not target_files:
        console.print(f"[bold red]Error:[/] No files found in {INPUT_DIR} with extensions {exts}")
        return

    for md_path in target_files:
        rel_path = md_path.relative_to(INPUT_DIR)
        inter_path = INTERMEDIATE_DIR / rel_path.with_suffix(".adoc")
        
        inter_path.parent.mkdir(parents=True, exist_ok=True)
        
        console.print(f"[bold blue]X-Phase:[/] [cyan]{rel_path}[/] -> [yellow]{inter_path.name}[/]")
        converter.convert_file(md_path, inter_path)

@app.command(name="y-repair")
def repair_y(
    file_name: Optional[str] = typer.Option(None, "--file", "-f"),
    fix: bool = typer.Option(True, "--fix/--no-fix"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """COMMAND Y: Validates and repairs AsciiDoc files with recursive directory mirroring."""
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    
    repair_engine = LinguisticEngine(knowledge_base=pipeline_config)
    audit_logger = AuditLogger()
    fixer = StyleFixer(config_path=config_path)

    if file_name:
        path_obj = Path(file_name)
        input_file = path_obj if path_obj.is_absolute() else INTERMEDIATE_DIR / file_name
        target_files = [input_file] if input_file.exists() else []
    else:
        target_files = list(INTERMEDIATE_DIR.rglob("*.adoc"))

    for inter_path in target_files:
        rel_path = inter_path.relative_to(INTERMEDIATE_DIR)
        final_path = OUTPUT_DIR / rel_path
        
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(inter_path, final_path)
        
        console.print(f"\n[bold blue]Y-Phase:[/] Validating [cyan]{rel_path}[/]")
        
        linter = StyleLinter(final_path, config_path=config_path)
        linter.setup_config()
        
        initial_findings = linter.run()
        linter.display_report(initial_findings)
        
        if fix and initial_findings:
            content = final_path.read_text(encoding="utf-8")
            healed = repair_engine.repair_text(content)
            final_path.write_text(healed, encoding="utf-8")
            
            file_key = str(final_path.resolve())
            fixer.fix_file(final_path, initial_findings.get(file_key, []))

            final_findings = linter.run()
            residual_violations = final_findings.get(file_key, [])
            
            initial_count = len(initial_findings.get(file_key, []))
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
            
            console.print(f"  [bold green]✨ Processing complete for {rel_path}.[/]")
            if residual_count > 0:
                console.print(f"  [bold green]{fixed_count} fixed.[/] [bold yellow]📋 {residual_count} items in audit log.[/]")
            else:
                console.print(f"  [bold green]✅ {fixed_count} fixed. Document is style-guide perfect![/]")

@app.command(name="full-run")
def execute_full_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file path"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Pull latest styles before running"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """THE COMBO COMMAND: Syncs, Converts, and Repairs while maintaining folder structure."""
    if sync:
        sync_styles(config=config)
    
    convert_x(file_name=file_name, config=config)
    
    adoc_target = None
    if file_name:
        # Map input filename to expected adoc filename for the repair phase
        adoc_target = str(Path(file_name).with_suffix(".adoc"))
        
    repair_y(file_name=adoc_target, fix=True, config=config)

def main():
    app()

if __name__ == "__main__":
    main()