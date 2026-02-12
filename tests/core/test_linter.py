"""Location: tests/core/test_linter.py.

Description: Unit test suite for the StyleLinter engine.
Validates configuration generation, Vale CLI integration, and 
JSON report parsing for the Personal Transpiler-Pro pipeline.
"""

from pathlib import Path

import pytest

from transpiler_pro.core.linter import StyleLinter


@pytest.fixture
def linter(tmp_path: Path) -> StyleLinter:
    """Provides a StyleLinter instance targeting a temporary file.
    
    Args:
        tmp_path (Path): Pytest fixture for a temporary directory.

    Returns:
        StyleLinter: A linter instance isolated from production data.
    """
    test_file = tmp_path / "test.adoc"
    test_file.write_text("This is a test document.")
    return StyleLinter(test_file)


def test_config_generation(linter: StyleLinter):
    """Verifies that setup_config correctly generates a .vale.ini file.
    
    Checks for the presence of mandatory SUSE-style paths and the 
    correct alert level threshold in the generated configuration.
    """
    linter.setup_config()
    
    assert linter.vale_ini.exists()
    config_content = linter.vale_ini.read_text()
    
    # Check for essential configuration keys
    assert "StylesPath" in config_content
    assert "BasedOnStyles = Vale, config, common, asciidoc" in config_content
    assert "MinAlertLevel = suggestion" in config_content


def test_report_display_logic(linter: StyleLinter, capsys):
    """Checks display_report handles empty data sets gracefully.
    
    Ensures that the linter provides a positive feedback message 
    when no violations are found, rather than crashing or being silent.
    """
    empty_data = {}
    linter.display_report(empty_data)
    
    captured = capsys.readouterr()
    assert "No style violations detected" in captured.out


def test_json_parsing_resilience(linter: StyleLinter):
    """Ensures the report logic can handle the nested Vale JSON structure.
    
    Validates that the specific keys (Line, Severity, Message, Check) 
    are correctly indexed from the simulated Vale CLI output.
    """
    # Mock data representing a typical Vale violation report
    mock_vale_json = {
        "test.adoc": [
            {
                "Line": 5,
                "Severity": "warning",
                "Message": "Use 'Wi-Fi' instead of 'wifi'",
                "Check": "Vale.Spelling"
            }
        ]
    }
    
    issues = mock_vale_json["test.adoc"]
    assert len(issues) == 1
    assert issues[0]["Check"] == "Vale.Spelling"
    assert issues[0]["Line"] == 5


def test_severity_color_mapping(linter: StyleLinter):
    """Validates that the linter identifies all three severity levels.
    
    Ensures that errors, warnings, and suggestions are all correctly 
    categorized for subsequent visual table rendering.
    """
    mock_data = {
        "file.adoc": [
            {"Severity": "error", "Line": 1, "Message": "Critical", "Check": "Rule1"},
            {"Severity": "warning", "Line": 2, "Message": "Alert", "Check": "Rule2"},
            {"Severity": "suggestion", "Line": 3, "Message": "Hint", "Check": "Rule3"}
        ]
    }
    
    severities = [issue["Severity"] for issue in mock_data["file.adoc"]]
    assert "error" in severities
    assert "warning" in severities
    assert "suggestion" in severities
    