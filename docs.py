"""
Location: docs.py
Description: Final Unified Portal Engine with dynamic timestamps and input cleanup.
"""

import subprocess
import sys
import shutil
import time
from pathlib import Path
from rich.console import Console

# Import markdown2 for real HTML rendering of the README
try:
    import markdown2
except ImportError:
    print("Please run: uv add markdown2")
    sys.exit(1)

console = Console()

def run_step(name: str, command: list):
    """Executes shell commands with styled output and error handling."""
    console.print(f"[bold blue]Step:[/] {name}...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        console.print(f"  [bold green]✓[/] {name} completed.")
    except subprocess.CalledProcessError as e:
        console.print(f"  [bold red]✗[/] {name} failed: {e.stderr or e.stdout}")
        if "pytest" not in name.lower() and "refining" not in name.lower():
            sys.exit(1)

def build_portal():
    """Main orchestration for generating the documentation portal."""
    project_root = Path(__file__).parent
    docs_out = project_root / "docs"
    
    # 0. Clean up transient input files to keep the directory tidy
    input_dir = project_root / "data" / "inputs"
    transient_files = ["System-Architecture.adoc", "System-Architecture.md"]
    for f_name in transient_files:
        f_path = input_dir / f_name
        if f_path.exists():
            f_path.unlink()
            console.print(f"[bold yellow]Cleaned up:[/] {f_name} from inputs.")

    if docs_out.exists():
        shutil.rmtree(docs_out)
    docs_out.mkdir(exist_ok=True)

    console.print("[bold magenta]🚀 Building Unified Documentation Portal[/]\n")

    # 1. API & Test Docs & Coverage
    run_step("Generating API Reference", ["uv", "run", "pdoc", "src/transpiler_pro", "-o", str(docs_out), "--docformat", "google"])
    run_step("Documenting Test Suite", ["uv", "run", "pdoc", "tests", "-o", str(docs_out), "--docformat", "google"])
    run_step("Generating Coverage Report", ["uv", "run", "pytest", "--cov=src", f"--cov-report=html:{docs_out}/coverage_report"])

    # 2. Architecture Refinement (Dogfooding)
    arch_src = project_root / "System-Architecture.adoc"
    arch_input = input_dir / "System-Architecture.adoc"
    
    if arch_src.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(arch_src, arch_input)
        run_step("Refining Architecture Docs", ["uv", "run", "transpiler-pro", "run", "--file", "System-Architecture.adoc", "--fix"])
    
    # 3. Path Management for Architecture Output
    arch_refined = project_root / "data" / "outputs" / "System-Architecture.adoc"
    arch_dest = docs_out / "System-Architecture.adoc"
    
    if arch_refined.exists():
        shutil.copy(str(arch_refined), str(arch_dest))
        console.print("  [bold green]✓[/] Architecture docs refined and moved to portal.")
    elif arch_src.exists():
        shutil.copy(str(arch_src), str(arch_dest))
        console.print("  [bold green]✓[/] Using original architecture.")
    
    # Final cleanup of input ADOC after processing
    if arch_input.exists():
        arch_input.unlink()

    # 4. Portal Generation
    create_home_page(project_root, docs_out)
    create_adoc_viewer(docs_out)
    
    nojekyll_file = docs_out / ".nojekyll"
    nojekyll_file.touch()
    console.print(f"  [bold green]✓[/] Jekyll bypass (.nojekyll) created at {nojekyll_file}")

    coverage_index = docs_out / "coverage_report" / "index.html"
    if coverage_index.exists():
        console.print(f"  [bold green]✓[/] Coverage report verified at {coverage_index}")

    console.print("\n[bold green]✨ Portal Ready![/]")

def create_home_page(root: Path, out: Path):
    """Generates the main entry point for the portal serving the README with a build timestamp."""
    readme_path = root / "README.md"
    readme_html = markdown2.markdown(readme_path.read_text(), extras=["fenced-code-blocks"]) if readme_path.exists() else "<h1>README not found.</h1>"
    
    # Adding a hidden timestamp to ensure the file hash changes every build
    build_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Transpiler-Pro Project Portal</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; margin: 0; background: #f6f8fa; }}
            nav {{ width: 280px; background: #24292e; color: white; height: 100vh; padding: 25px 20px; position: fixed; box-sizing: border-box; }}
            nav h2 {{ color: #42b983; border-bottom: 2px solid #42b983; padding-bottom: 10px; margin-top: 0; }}
            nav a {{ color: #c8d1d9; display: block; padding: 12px 0; text-decoration: none; border-bottom: 1px solid #30363d; font-size: 0.95rem; }}
            nav a:hover {{ color: #42b983; }}
            main {{ margin-left: 280px; padding: 40px; background: white; min-height: 100vh; width: calc(100% - 280px); box-sizing: border-box; }}
            .markdown-body {{ max-width: 900px; margin: 0 auto; line-height: 1.6; color: #24292e; }}
            pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; border: 1px solid #ddd; overflow: auto; }}
        </style>
    </head>
    <body>
        <nav>
            <h2>🚀 Navigation</h2>
            <a href="index.html">🏠 Home (README)</a>
            <a href="transpiler_pro.html">📦 API Reference</a>
            <a href="tests.html">🧪 Test Documentation</a>
            <a href="coverage_report/index.html">📊 Coverage Report</a>
            <a href="view-architecture.html">🏗️ System Architecture</a>
        </nav>
        <main>
            <article class="markdown-body">
                {readme_html}
                <hr>
                <p style="font-size: 0.8rem; color: #888;">Portal Last Updated: {build_time}</p>
            </article>
        </main>
    </body>
    </html>
    """
    (out / "index.html").write_text(html_content)

def create_adoc_viewer(out: Path):
    """Creates a wrapper page to safely render AsciiDoc content via JavaScript."""
    viewer_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Architecture Viewer</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/asciidoctor.js/1.5.9/asciidoctor.min.js"></script>
        <style>
            body { font-family: -apple-system, sans-serif; padding: 40px; max-width: 1000px; margin: 0 auto; background: #fff; line-height: 1.5; }
            .back-link { margin-bottom: 30px; display: inline-block; color: #42b983; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <a href="index.html" class="back-link">← Back to Portal</a>
        <div id="content">Loading Architecture...</div>
        <script>
            const asciidoctor = Asciidoctor();
            fetch('System-Architecture.adoc')
                .then(response => {
                    if (!response.ok) throw new Error('File not found');
                    return response.text();
                })
                .then(data => {
                    document.getElementById('content').innerHTML = asciidoctor.convert(data, { 
                        'attributes': { 'showtitle': true, 'icons': 'font', 'sectanchors': true } 
                    });
                })
                .catch(err => {
                    document.getElementById('content').innerHTML = '<p style="color:red">Error: ' + err.message + '</p>';
                });
        </script>
    </body>
    </html>
    """
    (out / "view-architecture.html").write_text(viewer_content)

if __name__ == "__main__":
    build_portal()