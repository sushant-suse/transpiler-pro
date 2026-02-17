"""Location: tests/core/test_fixer.py
Description: Unit tests for the NLP-aware StyleFixer logic using isolated config.
"""

import pytest
from pathlib import Path
from transpiler_pro.core.fixer import StyleFixer

@pytest.fixture
def fixer(tmp_path: Path) -> StyleFixer:
    """Provides a StyleFixer instance with a mocked pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    # Using raw string to avoid escaping issues in the test environment
    pyproject.write_text(r"""
    [tool.transpiler-pro.branding]
    suse = "SUSE"
    wifi = "Wi-Fi"
    ip = "IP"
    setup = "setting up"

    [tool.transpiler-pro.patterns]
    suggestion_extraction = "'(.*?)'"
    instead_of_trigger = "instead of"
    removal_trigger = "removing"

    [tool.transpiler-pro.grammar]
    special_verbs = { "setup" = "setting up" }
    plural_triggers = ["we", "they", "you", "NNS", "NNPS"]
    cvc_doubles = ["run", "set", "get", "stop", "plan"]
    """)
    # Inject the temporary config path into the constructor
    return StyleFixer(config_path=pyproject)

def test_fix_grammar_aware_will_singular(fixer, tmp_path):
    """Verifies singular subject 'The system' uses 'is' and conjugates the verb."""
    adoc_file = tmp_path / "test1.adoc"
    adoc_file.write_text("The system will reboot.")
    
    violations = [{"Line": 1, "Check": "common.Will", "Message": "Avoid using 'will'"}]
    fixer.fix_file(adoc_file, violations)
    
    # NLP Result: Future Tense -> Progressive Present
    assert "The system is rebooting." in adoc_file.read_text()

def test_fix_grammar_aware_will_plural(fixer, tmp_path):
    """Verifies plural subject 'We' uses 'are' and conjugates the verb."""
    adoc_file = tmp_path / "test2.adoc"
    adoc_file.write_text("We will check the connection.")
    
    violations = [{"Line": 1, "Check": "common.Will", "Message": "Avoid using 'will'"}]
    fixer.fix_file(adoc_file, violations)
    
    assert "We are checking the connection." in adoc_file.read_text()

def test_fix_generic_removal(fixer, tmp_path):
    """Verifies that 'Consider removing X' works via dynamic config triggers."""
    adoc_file = tmp_path / "test3.adoc"
    adoc_file.write_text("It is very easy.")
    
    violations = [{
        "Line": 1,
        "Check": "common.Editorializing",
        "Message": "Consider removing 'very'"
    }]
    fixer.fix_file(adoc_file, violations)
    
    # Ensures word and trailing space are removed to avoid double spaces
    assert adoc_file.read_text().strip() == "It is easy."

def test_fix_generic_replacement_pattern(fixer, tmp_path):
    """Verifies 'Consider using X instead of Y' works via dynamic config triggers."""
    adoc_file = tmp_path / "test4.adoc"
    adoc_file.write_text("Check the advanced config.")
    
    violations = [{
        "Line": 1,
        "Check": "common.TermwebTerms",
        "Message": "Consider using 'configuration' instead of 'config'"
    }]
    fixer.fix_file(adoc_file, violations)
    
    assert "advanced configuration" in adoc_file.read_text()

def test_fix_case_insensitivity_on_spelling(fixer, tmp_path):
    """Verifies that suggestion extraction works regardless of input case."""
    adoc_file = tmp_path / "test5.adoc"
    adoc_file.write_text("Running suse systems.")
    
    violations = [{
        "Line": 1,
        "Check": "Vale.Spelling",
        "Message": "Did you really mean 'suse'?",
        "Suggestion": "SUSE"
    }]
    fixer.fix_file(adoc_file, violations)
    
    assert "SUSE systems" in adoc_file.read_text()

def test_fix_branding_catch_all(fixer, tmp_path):
    """Verifies the brute-force branding pass for terms without linter violations."""
    adoc_file = tmp_path / "test6.adoc"
    adoc_file.write_text("setup suse with wifi on ip.")
    
    # Branding pass runs regardless of violations list
    fixer.fix_file(adoc_file, [])
    
    content = adoc_file.read_text()
    assert "SUSE" in content
    assert "Wi-Fi" in content
    assert "IP" in content
    assert "setting up" in content

def test_fix_special_verb_conjugation(fixer, tmp_path):
    """Verifies special cases like 'setup' mapping to 'setting up' from config."""
    adoc_file = tmp_path / "test7.adoc"
    adoc_file.write_text("We will setup the server.")
    
    violations = [{"Line": 1, "Check": "common.Will", "Message": "Avoid using 'will'"}]
    fixer.fix_file(adoc_file, violations)
    
    # Result uses the 'special_verbs' override from TOML
    assert "We are setting up the server." in adoc_file.read_text()