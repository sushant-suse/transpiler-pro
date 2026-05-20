"""
Location: tests/test_cli.py

Description: Functional tests for the Transpiler-Pro Orchestration Layer.

Focuses on verifying that the CLI correctly coordinates the sync, 
conversion, and refinement phases while mocking external side effects 
to ensure isolated, high-speed test execution.
"""

import pytest
from transpiler_pro.cli import execute_full_pipeline, app
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
    monkeypatch.setattr("transpiler_pro.cli.INTERMEDIATE_DIR", tmp_path / "intermediate")
    monkeypatch.setattr("transpiler_pro.cli.OUTPUT_DIR", out_dir)
    
    # Mock config loader to avoid disk I/O issues
    monkeypatch.setattr("transpiler_pro.cli.load_config", lambda x: {
        "pipeline": {"supported_extensions": [".md"]},
        "antora": {"headers": [":toc:"]}
    })

    return {"in": in_dir, "out": out_dir, "tmp": tmp_path}


@pytest.fixture
def pipeline_spies(monkeypatch):
    """Mocks side-effectful pipeline steps and captures orchestration arguments."""
    calls = {"sync": 0, "repair_file_name": None, "audit": 0}

    def _sync_styles(**kwargs):
        calls["sync"] += 1

    def _convert_x(**kwargs):
        return None

    def _repair_y(**kwargs):
        calls["repair_file_name"] = kwargs.get("file_name")

    def _audit_pipeline(**kwargs):
        calls["audit"] += 1

    monkeypatch.setattr("transpiler_pro.cli.sync_styles", _sync_styles)
    monkeypatch.setattr("transpiler_pro.cli.convert_x", _convert_x)
    monkeypatch.setattr("transpiler_pro.cli.repair_y", _repair_y)
    monkeypatch.setattr("transpiler_pro.cli.audit_pipeline", _audit_pipeline)
    monkeypatch.setattr("transpiler_pro.cli.generate_master_attributes", lambda **kwargs: None)

    return calls

def test_cli_help():
    """CLI wrapper check (this usually works even when 'run' fails)."""
    result = runner.invoke(app, ["full-run", "--help"])
    assert result.exit_code == 0

def test_logic_sync_invocation(logic_setup, pipeline_spies):
    """Ensures the full pipeline calls style sync when enabled."""
    execute_full_pipeline(
        file_name=None,
        sync=True,
        audit=False,
        input_path=logic_setup["in"],
        output_path=logic_setup["out"],
        config=str(logic_setup["tmp"] / "fake.toml"),
    )
    assert pipeline_spies["sync"] == 1

def test_logic_run_empty_dir(logic_setup, pipeline_spies):
    """Ensures audit can be disabled for a no-op run."""
    execute_full_pipeline(
        file_name=None,
        sync=False,
        audit=False,
        input_path=logic_setup["in"],
        output_path=logic_setup["out"],
        config=str(logic_setup["tmp"] / "fake.toml"),
    )
    assert pipeline_spies["audit"] == 0

def test_logic_full_orchestration(logic_setup, pipeline_spies):
    """Ensures markdown targets are mapped to .adoc for Y-phase repair."""
    execute_full_pipeline(
        file_name="test.md",
        sync=False,
        audit=False,
        input_path=logic_setup["in"],
        output_path=logic_setup["out"],
        config=str(logic_setup["tmp"] / "fake.toml"),
    )
    assert pipeline_spies["repair_file_name"] == "test.adoc"
