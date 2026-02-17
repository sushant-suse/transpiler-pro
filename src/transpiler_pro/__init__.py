"""
Location: src/transpiler_pro/__init__.py

Description: Transpiler-Pro - Enterprise Documentation Pipeline.

This package provides a comprehensive engine for converting Markdown to 
AsciiDoc while enforcing linguistic standards and branding consistency.

Core Features:

1. **DocConverter**: Shield-Transpile-Restore logic using Pandoc.
2. **StyleLinter**: Orchestration of Vale-based style validation.
3. **StyleFixer**: NLP-driven 'Auto-Heal' for linguistic repair.

The pipeline is entirely data-driven, utilizing settings defined in `pyproject.toml`.
"""

from .core.converter import DocConverter
from .core.linter import StyleLinter
from .core.fixer import StyleFixer

__version__ = "1.0.0"
__author__ = "Sushant Gaurav"


def get_info() -> str:
    """
    Returns the basic identity string for the package.

    Returns:
        str: A formatted string containing the tool name, version, and purpose.
    """
    return f"Transpiler-Pro v{__version__} - Enterprise Documentation Engine"


# Defines the public API exposed at the top level of the package
__all__ = [
    "DocConverter", 
    "StyleLinter", 
    "StyleFixer", 
    "__version__", 
    "get_info"
]