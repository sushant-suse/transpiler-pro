"""
Location: tests/test_fixer.py

Description: Functional tests for the NLP-driven 'Auto-Heal' Fixer engine.

Focuses on verifying that linguistic violations are repaired, tense shifting 
logic is accurate, and the Learning Engine correctly updates the JSON brain.
"""

import json
import pytest
from transpiler_pro.core.fixer import StyleFixer

@pytest.fixture
def mock_fixer(tmp_path):
    """
    Sets up a StyleFixer with a temporary environment and isolated Knowledge Base.
    """
    # 1. Create a dummy pyproject.toml with grammar and pattern settings
    cfg = tmp_path / "pyproject.toml"
    kb_path = tmp_path / "data" / "kb.json"
    
    cfg.write_text(f"""
    [tool.transpiler-pro.pipeline]
    knowledge_base = "{kb_path}"

    [tool.transpiler-pro.grammar]
    special_verbs = {{ "reboot" = "rebooting" }}

    [tool.transpiler-pro.patterns]
    suggestion_extraction = "'(.*?)'"
    removal_trigger = "removing"
    """)
    
    # 2. Initialize the Knowledge Base directory and file
    kb_path.parent.mkdir(parents=True)
    kb_path.write_text(json.dumps({
        "branding": {"id": "ID", "suse": "SUSE"},
        "learned": {}
    }))
    
    return StyleFixer(config_path=cfg)

def test_fixer_tense_shift_logic(mock_fixer):
    """Verifies NLP tense shifting: 'will [verb]' -> 'is/are [progressive]'."""
    # Skip if NLP model isn't loaded to avoid CI failure
    if not mock_fixer.nlp:
        pytest.skip("spaCy model 'en_core_web_sm' not found.")

    line_singular = "The system will reboot."
    line_plural = "We will test the system."

    assert "is rebooting" in mock_fixer._fix_tense(line_singular)
    assert "are testing" in mock_fixer._fix_tense(line_plural)

def test_special_verb_override(mock_fixer):
    """Ensures TOML special_verbs take priority over algorithmic -ing rules."""
    if not mock_fixer.nlp:
        pytest.skip("spaCy model not found.")
        
    # We defined 'reboot' -> 'rebooting' in the fixture TOML
    doc = mock_fixer.nlp("reboot")
    verb_token = doc[0]
    
    result = mock_fixer._get_progressive_verb(verb_token)
    assert result == "rebooting"

def test_branding_and_learning_discovery(mock_fixer, tmp_path):
    """Tests that the fixer repairs branding and logs new words to 'learned'."""
    test_file = tmp_path / "output.adoc"
    # Ensure 'kramdoc' is in the text so regex has something to find
    test_file.write_text("Check the id of suse linux and kramdoc.")
    
    violations = [
        {"Line": 1, "Message": "Use 'SUSE' instead of 'suse'", "Check": "SUSE.Branding"},
        {"Line": 1, "Message": "Spelling error: 'kramdoc'", "Check": "Vale.Spelling"}
    ]
    
    mock_fixer.fix_file(test_file, violations)
    content = test_file.read_text()
    
    assert "ID" in content
    assert "SUSE" in content
    assert "Kramdoc" in content 
    
    # Check Learning Engine
    updated_kb = json.loads(mock_fixer.kb_path.read_text())
    assert "kramdoc" in updated_kb["learned"]
    assert updated_kb["learned"]["kramdoc"] == "Kramdoc"

def test_surgical_removal(mock_fixer, tmp_path):
    """Verifies that the fixer can remove words based on 'removal' triggers."""
    test_file = tmp_path / "test.adoc"
    test_file.write_text("This is very important.")
    
    violations = [{
        "Line": 1, 
        "Message": "Consider removing 'very'", 
        "Check": "SUSE.Very"
    }]
    
    mock_fixer.fix_file(test_file, violations)
    assert "This is important." in test_file.read_text()