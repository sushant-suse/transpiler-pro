"""Location: tests/test_cli.py
Description: Functional tests for the robust, conversion-focused Typer CLI.
"""

from pathlib import Path
from typer.testing import CliRunner
import pytest
from transpiler_pro.cli import app

runner = CliRunner()

@pytest.fixture
def mock_env(tmp_path, monkeypatch):
    """Sets up a robust temporary environment with a mock pyproject.toml."""
    # 1. Create a dummy pyproject.toml with all required sections
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.transpiler-pro.pipeline]
supported_extensions = [".md"]

[tool.transpiler-pro.antora]
headers = [":experimental:", ":toc:"]

[tool.transpiler-pro.conversions]
admonition_map = { note = "NOTE" }
extension_map = { md = "adoc" }
shielding_patterns = []
cleanup_regex = []

[tool.transpiler-pro.branding]
suse = "SUSE"

[tool.transpiler-pro.patterns]
suggestion_extraction = "'(.*?)'"
    """)

    # 2. Force the CLI and its engines to use this temp directory
    # We patch the path utils to point to our isolated tmp_path
    monkeypatch.setattr("transpiler_pro.cli.INPUT_DIR", tmp_path)
    monkeypatch.setattr("transpiler_pro.cli.OUTPUT_DIR", tmp_path)
    
    # CRITICAL: We monkeypatch 'load_config' in cli.py to return our temp config
    import tomllib
    def mock_load_config():
        with open(pyproject, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("transpiler-pro", {})
    
    monkeypatch.setattr("transpiler_pro.cli.load_config", mock_load_config)
    
    # Also ensure the individual classes look at this pyproject.toml
    monkeypatch.setattr("transpiler_pro.core.converter.Path", lambda x: pyproject if "pyproject.toml" in str(x) else Path(x))
    monkeypatch.setattr("transpiler_pro.core.fixer.Path", lambda x: pyproject if "pyproject.toml" in str(x) else Path(x))
    monkeypatch.setattr("transpiler_pro.core.linter.Path", lambda x: pyproject if "pyproject.toml" in str(x) else Path(x))
    
    return tmp_path

def test_cli_help():
    """Ensures the help menu renders correctly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Personal Transpiler-Pro" in result.output

def test_cli_run_empty_dir(mock_env):
    """Ensures handled gracefully when no files exist."""
    # The run command now checks INPUT_DIR, which is mocked to tmp_path (empty)
    result = runner.invoke(app, ["run"])
    assert "No source files detected" in result.output

def test_cli_refine_command(mock_env):
    """Tests the bulk refinement logic using TOML headers."""
    # Create a dummy output file in our mocked OUTPUT_DIR
    adoc_file = mock_env / "test.adoc"
    adoc_file.write_text("= Title")
    
    result = runner.invoke(app, ["refine"])
    
    assert result.exit_code == 0
    content = adoc_file.read_text()
    assert ":experimental:" in content
    assert ":toc:" in content

def test_full_pipeline_logic(mock_env, monkeypatch):
    """Verifies the orchestrator moves through all phases."""
    # Setup a mock input in the mocked INPUT_DIR
    test_md = mock_env / "test.md"
    test_md.write_text("# Hello\nWe will test.")
    
    # Mock the linter and converter calls to avoid external binary dependencies (vale/kramdoc)
    # This makes the CLI test a pure "orchestration" test.
    monkeypatch.setattr("transpiler_pro.core.converter.DocConverter.convert_file", 
                        lambda self, src, dest: dest.write_text("= Hello\nWe are testing."))
    monkeypatch.setattr("transpiler_pro.core.linter.StyleLinter.run", lambda self: {})
    
    result = runner.invoke(app, ["run", "--file", "test.md"])
    
    assert result.exit_code == 0
    assert "Phase 1: Transforming" in result.output
    assert "Phase 2: Validating" in result.output
    assert (mock_env / "test.adoc").exists()