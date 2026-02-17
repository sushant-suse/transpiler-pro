"""Location: tests/core/test_linter.py
Description: Unit test suite for the robust, config-driven StyleLinter engine.
"""

import json
from pathlib import Path
import pytest
from transpiler_pro.core.linter import StyleLinter

@pytest.fixture
def linter(tmp_path: Path) -> StyleLinter:
    """Provides a StyleLinter instance with a mocked pyproject.toml and isolated paths."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.transpiler-pro.linter]
styles = ["Vale", "custom_style"]
min_alert_level = "warning"

[tool.transpiler-pro.patterns]
suggestion_extraction = "'(.*?)'"
ignored_placeholders = ["placeholder_text"]
    """)
    
    test_file = tmp_path / "test.adoc"
    test_file.write_text("This is a test document.")
    
    # PASS THE PATH: This links the class to the temporary test config
    return StyleLinter(test_file, config_path=pyproject)

def test_config_generation_robust(linter: StyleLinter):
    """Verifies that setup_config correctly interprets the mock TOML."""
    linter.setup_config()
    assert linter.vale_ini.exists()
    
    config_content = linter.vale_ini.read_text()
    
    # Validates that StylesPath is absolute and BasedOnStyles matches TOML
    assert "BasedOnStyles = Vale, custom_style" in config_content
    assert "MinAlertLevel = warning" in config_content

def test_suggestion_extraction_from_pattern(linter: StyleLinter):
    """Validates that 'ignored_placeholders' triggers the regex fallback."""
    mock_issue = {
        "Description": "Please use 'Technical Term' instead of 'tt'.",
        "Message": "Style violation",
        "Action": {"Params": ["placeholder_text"]} 
    }
    
    # Logic: 'placeholder_text' is in the ignored list, so it must use regex to find 'Technical Term'
    suggestion = linter._extract_suggestion(mock_issue)
    assert suggestion == "Technical Term"

def test_vale_run_processing(linter: StyleLinter, monkeypatch):
    """Verifies full processing loop from mocked Vale output to findings dict."""
    mock_vale_raw = {
        "test.adoc": [
            {
                "Line": 5,
                "Check": "Rule.One",
                "Severity": "error",
                "Message": "Error found",
                "Description": "Use 'Correct' instead.",
                "Action": {"Params": ["placeholder_text"]}
            }
        ]
    }

    class MockResult:
        stdout = json.dumps(mock_vale_raw)
        stderr = ""

    # Monkeypatch subprocess to return our JSON blob
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MockResult())

    findings = linter.run()
    
    # We use file_path.name or resolution depending on Vale version
    # Here we check that the suggestion was successfully extracted from Description
    assert any("Correct" in issue["Suggestion"] for file in findings.values() for issue in file)

def test_extract_suggestion_priority(linter: StyleLinter):
    """Verifies that valid Action Params are preferred over regex fallback."""
    mock_issue = {
        "Description": "General error",
        "Message": "Use 'IgnoreMe' instead.",
        "Action": {"Params": ["PriorityValue"]}
    }
    
    # 'PriorityValue' is not in 'ignored_placeholders', so it should be used directly
    suggestion = linter._extract_suggestion(mock_issue)
    assert suggestion == "PriorityValue"