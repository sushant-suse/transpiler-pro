"""
Location: tests/test_linter.py

Description: Functional tests for the Data-driven StyleLinter engine.

Focuses on configuration generation accuracy and processing of JSON 
output from the Vale CLI.
"""

import json
import pytest
from transpiler_pro.core.linter import StyleLinter

@pytest.fixture
def mock_linter(tmp_path):
    """Provides a StyleLinter configured with a temporary config environment."""
    cfg = tmp_path / "pyproject.toml"
    cfg.write_text("""
[tool.transpiler-pro.linter]
styles = ["SUSE", "Vale"]
min_alert_level = "warning"
theme = { error = "red", warning = "yellow" }

[tool.transpiler-pro.patterns]
suggestion_extraction = "'(.*?)'"
    """)
    target = tmp_path / "test.adoc"
    target.write_text("= Test Content")
    
    return StyleLinter(target_path=target, config_path=cfg)

def test_config_generation(mock_linter):
    """Verifies that .vale.ini is generated according to TOML settings."""
    mock_linter.setup_config()
    assert mock_linter.vale_ini.exists()
    
    content = mock_linter.vale_ini.read_text()
    assert "BasedOnStyles = SUSE, Vale" in content
    assert "MinAlertLevel = warning" in content

def test_suggestion_extraction(mock_linter):
    """Ensures suggestions are correctly parsed from linter messages."""
    issue = {
        "Message": "Use 'SUSE' instead of 'suse'",
        "Description": "Linguistic branding check",
        "Action": {"Params": ["SUSE"]}
    }
    
    suggestion = mock_linter._extract_suggestion(issue)
    assert suggestion == "SUSE"

def test_run_with_mocked_vale(mock_linter, monkeypatch):
    """Verifies that run() processes JSON output into our internal finding format."""
    import subprocess
    
    # Mock Vale JSON output
    mock_output = json.dumps({
        str(mock_linter.target_path.resolve()): [
            {
                "Line": 5,
                "Check": "SUSE.Branding",
                "Severity": "error",
                "Message": "Use 'ID' instead of 'id'"
            }
        ]
    })
    
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: 
                        subprocess.CompletedProcess(args, 0, stdout=mock_output))
    
    findings = mock_linter.run()
    
    assert len(findings) == 1
    key = list(findings.keys())[0]
    assert findings[key][0]["Line"] == 5
    assert findings[key][0]["Suggestion"] == "ID"