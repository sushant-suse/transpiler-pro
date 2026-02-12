"""Location: tests/core/test_converter.py.

Description: Unit test suite for the DocConverter transformation engine.
Validates structural integrity and deterministic regex mapping.
"""

import pytest

from transpiler_pro.core.converter import DocConverter


@pytest.fixture
def converter() -> DocConverter:
    """Provides a fresh instance of the DocConverter for isolated unit testing.
    
    Returns:
        DocConverter: A clean instance of the conversion engine.
    """
    return DocConverter()


def test_admonition_transformation(converter: DocConverter):
    """Verifies conversion of ':::' blocks to formal AsciiDoc admonitions.
    
    Ensures that the triple-colon syntax is correctly shielded and then 
    restored into a delimited AsciiDoc block with the correct type mapping.
    """
    md_input = ":::note\nSystem update required.\n:::"
    
    shielded = converter.pre_process_markdown(md_input)
    result = converter.post_process_asciidoc(shielded)
    
    assert "[NOTE]" in result
    assert "====" in result
    assert "System update required." in result


def test_link_to_xref_normalization(converter: DocConverter):
    """Validates that internal links are sanitized and converted to Antora XREFs.
    
    Checks that leading relative prefixes ('./') are stripped and Markdown 
    extensions are mapped to the AsciiDoc equivalent.
    """
    adoc_input = "Reference the link:./setup/install.md[Manual]."
    
    result = converter.post_process_asciidoc(adoc_input)
    
    assert "xref:setup/install.adoc[Manual]" in result
    assert "link:" not in result


def test_collapsible_summary_preservation(converter: DocConverter):
    """Ensures HTML details elements are converted to [%collapsible] blocks.
    
    Validates the 'Marker Strategy' for titles containing spaces and 
    confirms content preservation within the restored block.
    """
    md_input = "<details><summary>Debug Logs</summary>Log entry 123</details>"
    
    shielded = converter.pre_process_markdown(md_input)
    result = converter.post_process_asciidoc(shielded)
    
    assert "[%collapsible]" in result
    assert ".Debug Logs" in result
    assert "Log entry 123" in result


def test_internal_heading_protection(converter: DocConverter):
    """Verifies that headings inside blocks are demoted to prevent syntax breakage.
    
    Checks the 'Admonition Safety' logic that converts nested '=' headings 
    into bold text to avoid collision with block delimiters.
    """
    shielded_input = "MARKER_ADMON_START_info\n==== Warning Header\nData\nMARKER_ADMON_END"
    
    result = converter.post_process_asciidoc(shielded_input)
    
    assert "[IMPORTANT]" in result
    assert "*Warning Header*" in result
    assert "==== Warning Header" not in result


def test_nested_list_normalization(converter: DocConverter):
    """Ensures mixed-type lists are converted with proper depth levels.
    
    Validates the logic that converts single-dot numbered lists into 
    double-dot nested lists when they follow a bulleted parent.
    """
    adoc_input = "* Top level bullet\n. Nested numbered item"
    
    result = converter.post_process_asciidoc(adoc_input)
    
    assert "* Top level bullet" in result
    assert ".. Nested numbered item" in result