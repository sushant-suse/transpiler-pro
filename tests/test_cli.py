"""
Location: tests/test_cli.py

Description: Functional tests for the Transpiler-Pro Orchestration Layer.

Focuses on verifying that the CLI correctly coordinates the sync, 
conversion, and refinement phases while mocking external side effects 
to ensure isolated, high-speed test execution.
"""

import pytest
from transpiler_pro.cli import run_pipeline, app
from typer.testing import CliRunner

runner = CliRunner()

@pytest.fixture
def logic_setup(tmp_path, monkeypatch):
    """Sets up physical paths and mocks for logic-level testing."""
    in_dir = tmp_path / "inputs"
    out_dir = tmp_path / "outputs"
    in_dir.mkdir()
    out_dir.mkdir()

    monkeypatch.setattr("transpiler_pro.cli.INPUT_DIR", in_dir)
    monkeypatch.setattr("transpiler_pro.cli.OUTPUT_DIR", out_dir)
    
    # Mock config loader to avoid disk I/O issues
    monkeypatch.setattr("transpiler_pro.cli.load_config", lambda x: {
        "pipeline": {"supported_extensions": [".md"]},
        "antora": {"headers": [":toc:"]}
    })
    
    # Mock subprocess
    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
    
    return {"in": in_dir, "out": out_dir, "tmp": tmp_path}

def test_cli_help():
    """CLI wrapper check (this usually works even when 'run' fails)."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0

def test_logic_sync_invocation(logic_setup, capsys):
    """Tests the run_pipeline logic directly."""
    run_pipeline(sync=True, config_path=logic_setup["tmp"] / "fake.toml")
    captured = capsys.readouterr().out
    assert "Syncing SUSE Style Guide" in captured

def test_logic_run_empty_dir(logic_setup, capsys):
    """Tests the run_pipeline logic handles empty dirs."""
    run_pipeline(config_path=logic_setup["tmp"] / "fake.toml")
    captured = capsys.readouterr().out
    assert "No source files detected" in captured

def test_logic_full_orchestration(logic_setup, monkeypatch, capsys):
    """Tests the full logic flow from Markdown to AsciiDoc."""
    test_md = logic_setup["in"] / "test.md"
    test_md.write_text("# Hello")
    
    # Mock engines
    monkeypatch.setattr("transpiler_pro.core.converter.DocConverter.convert_file", 
                        lambda self, src, dest: dest.write_text("= Hello"))
    monkeypatch.setattr("transpiler_pro.core.linter.StyleLinter.run", lambda self: {})
    monkeypatch.setattr("transpiler_pro.core.linter.StyleLinter.setup_config", lambda self: None)
    monkeypatch.setattr("transpiler_pro.core.linter.StyleLinter.display_report", lambda self, x: None)
    
    run_pipeline(file_name="test.md", config_path=logic_setup["tmp"] / "fake.toml")
    
    assert (logic_setup["out"] / "test.adoc").exists()
    captured = capsys.readouterr().out
    assert "Phase 1" in captured