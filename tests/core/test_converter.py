"""
Location: tests/core/test_converter.py

Description: Tests for the DocConverter core engine.
"""

from pathlib import Path
import pytest
from transpiler_pro.core.converter import DocConverter

@pytest.fixture
def converter(tmp_path):
    """Fixture to provide a converter with a mock pyproject.toml."""
    cfg = tmp_path / "pyproject.toml"
    cfg.write_text("""
[tool.transpiler-pro.conversions]
extension_map = { md = "adoc" }
shielding_patterns = [
    { regex = ":::(?P<type>\\\\w+)\\\\n(?P<body>.*?)\\\\n:::", replacement = "MARKER_START_\\\\1\\n\\\\2\\nMARKER_END" }
]
restoration_patterns = [
    { regex = "MARKER_START_{key}\\\\n(.*?)\\\\nMARKER_END", replacement = "[{val}]\\n====\\n\\\\1\\n====", map = { note = "NOTE" } }
]
    """)
    return DocConverter(config_path=cfg)

def test_shielding_logic(converter):
    """Verifies that Markdown admonitions are correctly shielded."""
    content = ":::note\nThis is a note\n:::"
    result = converter.pre_process_markdown(content)
    assert "MARKER_START_note" in result

def test_restoration_logic(converter):
    """Verifies that markers are converted back to AsciiDoc syntax."""
    content = "MARKER_START_note\nThis is a note\nMARKER_END"
    result = converter.post_process_asciidoc(content)
    assert "[NOTE]" in result
    assert "====" in result

def test_pandoc_call_construction(converter, monkeypatch, tmp_path):
    """Verifies that convert_file constructs the correct Pandoc command."""
    import subprocess
    called_cmds = []
    
    def mock_run(cmd, **kwargs):
        called_cmds.append(cmd)
        # Find the output file path in the pandoc command (-o <path>)
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_text("Mock Output")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", mock_run)
    
    in_file = tmp_path / "input.md"
    in_file.write_text("# Test")
    out_file = tmp_path / "output.adoc"
    
    converter.convert_file(in_file, out_file)
    
    # Assert Pandoc was the chosen engine
    assert called_cmds[0][0] == "pandoc"
    assert "-f" in called_cmds[0]
    assert "markdown" in called_cmds[0]