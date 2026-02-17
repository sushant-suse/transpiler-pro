"""
Location: src/transpiler_pro/utils/paths.py

Description: Global Path Registry for Transpiler-Pro.

This module centralizes the filesystem logic, ensuring that all core engines 
(Converter, Linter, Fixer) use deterministic absolute paths. It also handles 
the automatic creation of the required directory infrastructure upon initialization.
"""

from pathlib import Path
from typing import List

# 1. Project Root Identification
# Resolves the absolute path to the project base (transpiler-pro/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent

# 2. Data Directory Definitions
# INPUT_DIR: Where source Markdown/MDX files reside.
# OUTPUT_DIR: Where finalized AsciiDoc files are generated.
DATA_DIR: Path = BASE_DIR / "data"
INPUT_DIR: Path = DATA_DIR / "inputs"
OUTPUT_DIR: Path = DATA_DIR / "outputs"

# 3. External Assets and Styles
# STYLES_DIR: Points to the localized SUSE style definitions and Vale rulesets.
STYLES_DIR: Path = BASE_DIR / "styles" / "suse-styles"


def initialize_directories() -> None:
    """
    Validates and creates the necessary directory infrastructure.

    This function ensures that the `data` and `styles` boundaries are ready 
    for I/O operations. It is executed automatically when the module is 
    imported to prevent FileNotFoundError during pipeline execution.
    """
    required_dirs: List[Path] = [
        INPUT_DIR,
        OUTPUT_DIR,
        STYLES_DIR.parent
    ]

    for directory in required_dirs:
        # 'parents=True' handles nested creation; 
        # 'exist_ok=True' prevents errors if already present.
        directory.mkdir(parents=True, exist_ok=True)


# Immediate execution ensures the filesystem is ready for the engines.
if __name__ != "__main__":
    initialize_directories()