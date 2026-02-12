"""Location: src/transpiler_pro/utils/paths.py.

Description: Global Path Registry for Personal Transpiler-Pro.
Centralizes filesystem logic and ensures the presence of required 
directory structures for the transpilation and linting pipelines.
"""

from pathlib import Path
from typing import List

# 1. Project Root Identification
# Resolves the absolute path to the project base (transpiler-pro/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent

# 2. Data Directory Definitions
DATA_DIR: Path = BASE_DIR / "data"
INPUT_DIR: Path = DATA_DIR / "inputs"
OUTPUT_DIR: Path = DATA_DIR / "outputs"

# 3. External Assets and Styles
# STYLES_DIR points to the localized SUSE style definitions and Vale rulesets.
STYLES_DIR: Path = BASE_DIR / "styles" / "suse-styles"


def initialize_directories() -> None:
    """Validates and creates the necessary directory infrastructure.

    This ensures the 'data' and 'styles' boundaries are ready for I/O operations.
    It creates missing folders for inputs, outputs, and styles using a 
    deterministic path resolution.
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


# Immediate execution of directory setup upon module import.
# This ensures that the filesystem is ready before any engine logic executes.
initialize_directories()
