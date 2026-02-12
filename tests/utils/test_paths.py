"""Location: tests/utils/test_paths.py.

Description: Unit test suite for the Global Path Registry.
Ensures that the project filesystem is correctly mapped and 
that core directories are initialized for I/O operations.
"""

from pathlib import Path

from transpiler_pro.utils import paths


def test_base_directory_resolution():
    """Verifies that the BASE_DIR correctly resolves to the project root.
    
    Checks for the presence of the 'src' directory and 'pyproject.toml' 
    to confirm the registry has identified the correct repository anchor.
    """
    assert paths.BASE_DIR.exists()
    assert (paths.BASE_DIR / "src").is_dir()
    assert (paths.BASE_DIR / "pyproject.toml").exists()


def test_data_directory_structure():
    """Ensures input and output paths are correctly defined.
    
    Validates that the directory registry points to the expected 
    sub-folders within the 'data/' hierarchy.
    """
    assert "data/inputs" in str(paths.INPUT_DIR)
    assert "data/outputs" in str(paths.OUTPUT_DIR)


def test_styles_directory_path():
    """Validates the path to the specialized SUSE rulesets.
    
    Ensures that the linter will look for style definitions in the 
    correct 'styles/suse-styles' location.
    """
    assert "styles/suse-styles" in str(paths.STYLES_DIR)


def test_directory_initialization():
    """Verifies the initialize_directories() idempotent logic.
    
    Confirms that the function successfully creates the mandatory 
    folder structure required for the application's I/O operations.
    """
    # Trigger initialization (though it runs on import, we test it explicitly)
    paths.initialize_directories()
    
    assert paths.INPUT_DIR.exists()
    assert paths.OUTPUT_DIR.exists()
    assert paths.STYLES_DIR.parent.exists()


def test_path_types():
    """Ensures all exported paths are instances of pathlib.Path.
    
    This is critical for cross-platform compatibility (Windows/macOS/Linux) 
    to ensure slash-normalization and path manipulation work correctly.
    """
    assert isinstance(paths.BASE_DIR, Path)
    assert isinstance(paths.INPUT_DIR, Path)
    assert isinstance(paths.OUTPUT_DIR, Path)