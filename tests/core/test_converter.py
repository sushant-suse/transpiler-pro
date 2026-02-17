"""Location: tests/core/test_converter.py
Description: Unit test suite for the robust, config-driven DocConverter engine.
"""

import pytest
from pathlib import Path
from transpiler_pro.core.converter import DocConverter

@pytest.fixture
def converter(tmp_path: Path) -> DocConverter:
    """Fixture that generates a mock pyproject.toml and initializes the converter."""
    pyproject = tmp_path / "pyproject.toml"
    
    # We use a raw string for the Python block, but double quotes for the TOML values
    config_content = r"""
    [tool.transpiler-pro.conversions]
    extension_map = { md = "adoc" }
    admonition_map = { note = "NOTE", info = "IMPORTANT" }

    shielding_patterns = [
        { regex = ":::(?P<type>\\w+)\\n(?P<body>.*?)\\n:::", replacement = "MARKER_ADMON_START_\\1\n\\2\nMARKER_ADMON_END" }
    ]

    cleanup_regex = [
        { regex = "^:.*?\\n", replacement = "", flags = "M" }
    ]
    """
    pyproject.write_text(config_content.strip())
    return DocConverter(config_path=pyproject)

def test_dynamic_shielding_logic(converter):
    """Verifies that the converter uses shielding regex from the mock TOML."""
    md_input = ":::note\nContent\n:::"
    shielded = converter.pre_process_markdown(md_input)
    
    assert "MARKER_ADMON_START_note" in shielded
    assert "Content" in shielded

def test_cleanup_regex_execution(converter):
    """Verifies that post-process cleanup successfully removes metadata lines."""
    adoc_input = ":toc: true\nActual content starts here."
    result = converter.post_process_asciidoc(adoc_input)
    
    assert ":toc:" not in result
    assert "Actual content starts here." in result

def test_dynamic_extension_mapping(converter):
    """Verifies that internal links are mapped to xrefs using the extension map."""
    adoc_input = "Check the link:./setup.md[Setup Guide]."
    result = converter.post_process_asciidoc(adoc_input)
    assert "xref:setup.adoc[Setup Guide]" in result