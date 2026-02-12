"""Location: src/transpiler_pro/__init__.py.

Description: Package initialization for Personal Transpiler-Pro.
Exposes the core API and version metadata for the transpilation engine.
"""

from .core.converter import DocConverter
from .core.linter import StyleLinter

__version__ = "1.0.0"
__author__ = "Sushant Gaurav"


def get_info() -> str:
    """Returns the basic identity string for the package.

    Returns:
        str: A formatted string containing the tool name and version.
    """
    return f"Personal Transpiler-Pro v{__version__} - Enterprise Documentation Engine"


# Add the submodules to the "all" list
__all__ = ["DocConverter", "StyleLinter", "__version__", "get_info", "core", "utils", "cli"]