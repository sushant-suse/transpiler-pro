"""
Location: src/transpiler_pro/cli.py
Description: The Orchestration Layer for Transpiler-Pro.

This module provides the Command Line Interface (CLI) using the Typer framework.
It manages the three primary phases of the documentation pipeline:
1. Sync: Updating the SUSE style rules.
2. X-Phase: Structural conversion (Markdown -> AsciiDoc).
3. Y-Phase: Linguistic repair and style validation (NLP & Vale).

The CLI ensures that directory structures are mirrored exactly from the 
'data/inputs' folder to 'data/outputs', supporting nested subfolders.
"""

import tomllib
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, List

import typer
from rich.console import Console

# Core logic imports
from transpiler_pro.core.converter import DocConverter
from transpiler_pro.core.fixer import StyleFixer
from transpiler_pro.core.linter import StyleLinter
from transpiler_pro.core.repair import LinguisticEngine

# Utility and Pathing imports
from transpiler_pro.utils.logger import AuditLogger
from transpiler_pro.utils.paths import INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR, STYLES_DIR

# Initialize Typer app and Rich console for styled terminal output
app = typer.Typer(
    name="transpiler-pro",
    help="Enterprise Documentation Pipeline with X (Convert) and Y (Repair) phases.",
    no_args_is_help=True, 
    add_completion=False
)
console = Console()

# Default configuration source
DEFAULT_CONFIG = Path("pyproject.toml")

def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Loads pipeline settings from the project's pyproject.toml file.

    Args:
        config_path (Path): Path to the TOML configuration file.

    Returns:
        Dict[str, Any]: A dictionary containing the [tool.transpiler-pro] settings.
    """
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            # We look specifically for the tool.transpiler-pro namespace
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/] {e}")
        return {}

@app.command(name="sync")
def sync_styles(config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")) -> None:
    """
    Synchronizes the local SUSE Style Guide repository with the official remote.

    This ensures the Vale linter uses the latest SUSE-approved linguistic rules.
    If a safe pull fails due to local cache corruption, it performs a fresh recovery clone.
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
            console.print("  [yellow]➜[/] Initializing Style Guide (Fresh Clone)...")
            subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True, capture_output=True)
        else:
            console.print("  [yellow]➜[/] Updating existing styles...")
            # Attempt a standard pull
            result = subprocess.run(
                ["git", "-C", str(target_dir), "pull", "origin", "master"], 
                capture_output=True, 
                text=True
            )
            
            # If pull fails (like it did for your teammate), wipe and re-clone
            if result.returncode != 0:
                console.print("  [bold yellow]⚠️ Warning:[/] Local cache out of sync. Attempting fresh recovery...")
                shutil.rmtree(target_dir)
                subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True, capture_output=True)
            
        console.print("  [bold green]✓[/] Style guide updated and ready.")
    except Exception as e:
        console.print(f"  [bold red]FATAL ERROR:[/] Could not synchronize styles. Details: {e}")
        raise typer.Exit(code=1)

@app.command(name="x-convert")
def convert_x(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file within the input directory"),
    input_path: Path = typer.Option(INPUT_DIR, "--input", "-i", help="Custom path to find input files"),
    output_path: Path = typer.Option(INTERMEDIATE_DIR, "--output", "-o", help="Custom path to store intermediate files"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    COMMAND X: Performs structural conversion or direct asset mirroring of Markdown to AsciiDoc.

    It scans the input directory recursively, processes all supported 
    extensions (.md, .mdx), and outputs raw .adoc files into the intermediate directory.
    
    Key Features:
    - Markdown files (.md, .mdx) are processed via the DocConverter.
    - All other files (e.g. .yml, .png, images) are copied directly to preserve structure.
    """
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    converter = DocConverter(config_path=config_path)

    # Resolve absolute paths for the provided input and output locations
    src_dir = Path(input_path).resolve()
    dest_dir = Path(output_path).resolve()

    # 1. Identify all target files (Capture ALL instead of just MD)
    all_files: List[Path] = []
    if file_name:
        path_obj = Path(file_name)
        input_file = path_obj if path_obj.is_absolute() else src_dir / file_name
        if input_file.exists():
            all_files = [input_file]
    else:
        # Walk through everything in the input directory
        all_files = [p for p in src_dir.rglob("*") if p.is_file()]

    if not all_files:
        console.print(f"[bold red]Error:[/] No files found in {src_dir}")
        return

    supported_exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])

    for src_path in all_files:
        # Calculate relative path to maintain folder depth based on the dynamic src_dir
        rel_path = src_path.relative_to(src_dir)
        
        # Branching Logic: Transform or Mirror
        if src_path.suffix.lower() in supported_exts:
            # --- CONVERSION BRANCH ---
            inter_path = dest_dir / rel_path.with_suffix(".adoc")
            inter_path.parent.mkdir(parents=True, exist_ok=True)
            
            console.print(f"[bold blue]X-Phase (Convert):[/] [cyan]{rel_path}[/] -> [yellow]{inter_path.name}[/]")
            converter.convert_file(src_path, inter_path)
        else:
            # --- MIRROR BRANCH ---
            # Copy non-markdown files (like _category_.yml, images, etc.) directly
            inter_path = dest_dir / rel_path
            inter_path.parent.mkdir(parents=True, exist_ok=True)
            
            console.print(f"[bold magenta]X-Phase (Mirror):[/] [cyan]{rel_path}[/]")
            shutil.copy2(src_path, inter_path)

@app.command(name="y-repair")
def repair_y(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific ADOC file within the intermediate directory"),
    input_path: Path = typer.Option(INTERMEDIATE_DIR, "--input", "-i", help="Custom path to find intermediate files"),
    output_path: Path = typer.Option(OUTPUT_DIR, "--output", "-o", help="Custom path to store final healed files"),
    fix: bool = typer.Option(True, "--fix/--no-fix", help="Enable/Disable automated linguistic healing"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    COMMAND Y: Validates and repairs AsciiDoc files linguistically.

    This phase applies:
    1. Linguistic Engine: Tense shifting and grammar correction via spaCy.
    2. Style Fixer: Resolves Vale linter violations and branding errors.
    3. Audit Logging: Records any remaining issues that require manual review.
    """
    config_path = Path(config)
    pipeline_config = load_config(config_path)
    
    repair_engine = LinguisticEngine(knowledge_base=pipeline_config)
    audit_logger = AuditLogger()
    fixer = StyleFixer(config_path=config_path)

    # Resolve absolute paths for the provided input and output locations
    src_dir = Path(input_path).resolve()
    dest_dir = Path(output_path).resolve()

    # Determine which files to process from the intermediate directory
    if file_name:
        path_obj = Path(file_name)
        input_file = path_obj if path_obj.is_absolute() else src_dir / file_name
        target_files = [input_file] if input_file.exists() else []
    else:
        # Capture all files (including .yml, images, etc.) to ensure mirroring from the dynamic src_dir
        target_files = [p for p in src_dir.rglob("*") if p.is_file()]

    for inter_path in target_files:
        # Calculate relative path based on the dynamic src_dir
        rel_path = inter_path.relative_to(src_dir)
        final_path = dest_dir / rel_path
        
        # Mirror structure to final output directory
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        # --- BRANCHING LOGIC: REPAIR OR MIRROR ---
        if inter_path.suffix.lower() == ".adoc":
            # 1. Standard AsciiDoc Repair Path
            shutil.copy2(inter_path, final_path)
            
            console.print(f"\n[bold blue]Y-Phase:[/] Validating [cyan]{rel_path}[/]")
            
            linter = StyleLinter(final_path, config_path=config_path)
            linter.setup_config()
            
            # First Pass: Identify violations
            initial_findings = linter.run()
            linter.display_report(initial_findings)
            
            if fix and initial_findings:
                # Linguistic Engine: Fix grammar/tense shifting
                content = final_path.read_text(encoding="utf-8")
                healed = repair_engine.repair_text(content)
                final_path.write_text(healed, encoding="utf-8")
                
                # Style Fixer: Fix spelling, branding, and linter-specific suggestions
                file_key = str(final_path.resolve())
                fixer.fix_file(final_path, initial_findings.get(file_key, []))

                # Second Pass: Verification and Audit Logging
                final_findings = linter.run()
                residual_violations = final_findings.get(file_key, [])
                
                # Reporting Stats
                initial_count = len(initial_findings.get(file_key, []))
                residual_count = len(residual_violations)
                fixed_count = initial_count - residual_count
                
                # Log any issues the machine couldn't fix for the human editor
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
        else:
            # 2. Asset Mirror Path
            console.print(f"[bold magenta]Y-Phase (Mirror):[/] [cyan]{rel_path}[/]")
            shutil.copy2(inter_path, final_path)

@app.command(name="full-run")
def execute_full_pipeline(
    file_name: Optional[str] = typer.Option(None, "--file", "-f", help="Target a specific file path"),
    input_path: Path = typer.Option(INPUT_DIR, "--input", "-i", help="Custom path to find source Markdown files"),
    output_path: Path = typer.Option(OUTPUT_DIR, "--output", "-o", help="Custom path to store final healed AsciiDoc files"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Pull latest styles before running"),
    config: str = typer.Option(str(DEFAULT_CONFIG), "--config", "-c")
) -> None:
    """
    THE COMBO COMMAND: Syncs, Converts, and Repairs in one atomic operation.
    
    This is the recommended command for production use. It handles the entire
    lifecycle of a document, maintaining folder structures and ensuring the 
    highest linguistic quality.
    """
    if sync:
        sync_styles(config=config)
    
    # 1. Run structural conversion
    # We always use INTERMEDIATE_DIR as the bridge for Phase X output
    convert_x(
        file_name=file_name, 
        input_path=input_path, 
        output_path=INTERMEDIATE_DIR, 
        config=config
    )
    
    # 2. Map input filename to expected intermediate filename for Phase Y
    # If it's a markdown file, Phase Y needs to look for the .adoc version
    # If it's an asset (like .yml), Phase Y looks for the original name
    target_name = None
    if file_name:
        path_obj = Path(file_name)
        pipeline_config = load_config(Path(config))
        supported_exts = pipeline_config.get("pipeline", {}).get("supported_extensions", [".md", ".mdx"])
        
        if path_obj.suffix.lower() in supported_exts:
            target_name = str(path_obj.with_suffix(".adoc"))
        else:
            target_name = file_name
        
    # 3. Run linguistic repair
    # We pull from INTERMEDIATE_DIR and save to the final user-defined output_path
    repair_y(
        file_name=target_name, 
        input_path=INTERMEDIATE_DIR, 
        output_path=output_path, 
        fix=True, 
        config=config
    )

def main():
    """Main entry point for the CLI."""
    app()

if __name__ == "__main__":
    main()