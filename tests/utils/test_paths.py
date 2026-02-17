"""
Location: tests/test_paths.py

Description: Unit tests for the Global Path Registry.

Ensures that project directories are correctly resolved and that the 
initialization logic creates the necessary folder structures.
"""

from transpiler_pro.utils import paths

def test_path_resolution():
    """Verifies that the BASE_DIR and subdirectories resolve to absolute paths."""
    assert paths.BASE_DIR.is_absolute()
    assert "transpiler-pro" in str(paths.BASE_DIR).lower()
    assert paths.INPUT_DIR.name == "inputs"
    assert paths.OUTPUT_DIR.name == "outputs"

def test_directory_initialization(tmp_path, monkeypatch):
    """Ensures that required directories are created if they don't exist."""
    # Mock DATA_DIR to a temporary path for isolated testing
    mock_data = tmp_path / "data"
    monkeypatch.setattr("transpiler_pro.utils.paths.DATA_DIR", mock_data)
    monkeypatch.setattr("transpiler_pro.utils.paths.INPUT_DIR", mock_data / "inputs")
    monkeypatch.setattr("transpiler_pro.utils.paths.OUTPUT_DIR", mock_data / "outputs")
    
    # Run initialization
    paths.initialize_directories()
    
    assert (mock_data / "inputs").exists()
    assert (mock_data / "outputs").exists()
    assert (mock_data / "inputs").is_dir()