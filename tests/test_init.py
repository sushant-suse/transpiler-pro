"""
Location: tests/test_init.py

Description: Unit tests for package-level metadata and API exposure.
"""

from transpiler_pro import __version__, get_info, DocConverter, StyleLinter, StyleFixer

def test_version_metadata():
    """Ensures the version string follows semantic versioning."""
    assert __version__ == "1.0.0"

def test_get_info_string():
    """Verifies the identity string contains the correct version and name."""
    info = get_info()
    assert "Transpiler-Pro" in info
    assert "1.0.0" in info

def test_api_exposure():
    """Ensures core engine classes are available directly from the package root."""
    assert DocConverter is not None
    assert StyleLinter is not None
    assert StyleFixer is not None