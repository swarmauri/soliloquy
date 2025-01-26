# tests/test_version_ops.py

import os
import tempfile
import shutil
import pytest
from unittest import mock
from soliloquy import version_ops
from packaging.version import Version, InvalidVersion

# Helper function to create a temporary pyproject.toml file
def create_temp_pyproject(version, extra_content=""):
    content = f"""
[tool.poetry]
name = "test-package"
version = "{version}"
description = "A test package"
authors = ["Test Author <test@example.com>"]

{extra_content}
"""
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return temp_dir, file_path

@pytest.fixture
def temp_pyproject():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file.
    """
    temp_dir, file_path = create_temp_pyproject("1.0.0")
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_extra():
    """
    Pytest fixture with extra content in pyproject.toml.
    """
    temp_dir, file_path = create_temp_pyproject("2.1.3", extra_content="""
[tool.poetry.dependencies]
requests = "^2.25.1"
""")
    yield file_path
    shutil.rmtree(temp_dir)

def test_read_pyproject_version(temp_pyproject):
    version, doc = version_ops.read_pyproject_version(temp_pyproject)
    assert version == "1.0.0"
    assert doc["tool"]["poetry"]["version"] == "1.0.0"

def test_read_pyproject_version_missing_version():
    # Create a temp pyproject.toml without version
    temp_dir, file_path = create_temp_pyproject(version="", extra_content="""
[tool.poetry]
name = "test-package"
description = "A test package"
authors = ["Test Author <test@example.com>"]
""")
    with pytest.raises(KeyError) as exc_info:
        version_ops.read_pyproject_version(file_path)
    assert "No version found under [tool.poetry]" in str(exc_info.value)
    shutil.rmtree(temp_dir)

def test_read_pyproject_version_invalid_file():
    with pytest.raises(FileNotFoundError):
        version_ops.read_pyproject_version("non_existent_directory/pyproject.toml")

def test_bump_version_major():
    new_version = version_ops.bump_version("1.2.3", "major")
    assert new_version == "2.0.0.dev1"

def test_bump_version_minor():
    new_version = version_ops.bump_version("1.2.3", "minor")
    assert new_version == "1.3.0.dev1"

def test_bump_version_patch():
    new_version = version_ops.bump_version("1.2.3", "patch")
    assert new_version == "1.2.4.dev1"

def test_bump_version_patch_dev():
    new_version = version_ops.bump_version("1.2.3.dev2", "patch")
    assert new_version == "1.2.3.dev3"

def test_bump_version_finalize():
    new_version = version_ops.bump_version("1.2.3.dev2", "finalize")
    assert new_version == "1.2.3"

def test_bump_version_finalize_non_dev():
    with pytest.raises(ValueError) as exc_info:
        version_ops.bump_version("1.2.3", "finalize")
    assert "Current version is stable; nothing to finalize." in str(exc_info.value)

def test_bump_version_invalid_bump_type():
    with pytest.raises(ValueError) as exc_info:
        version_ops.bump_version("1.2.3", "invalid")
    assert "bump_type must be one of" in str(exc_info.value)

def test_bump_version_invalid_current_version():
    with pytest.raises(ValueError) as exc_info:
        version_ops.bump_version("invalid_version", "patch")
    assert "Invalid current version" in str(exc_info.value)

def test_validate_and_set_version_higher():
    new_version = version_ops.validate_and_set_version("1.0.0", "1.1.0")
    assert new_version == "1.1.0"

def test_validate_and_set_version_same():
    new_version = version_ops.validate_and_set_version("1.0.0", "1.0.0")
    assert new_version == "1.0.0"

def test_validate_and_set_version_lower():
    with pytest.raises(ValueError) as exc_info:
        version_ops.validate_and_set_version("1.1.0", "1.0.0")
    assert "You cannot bump the version downwards" in str(exc_info.value)

def test_validate_and_set_version_invalid_new_version():
    with pytest.raises(ValueError) as exc_info:
        version_ops.validate_and_set_version("1.0.0", "invalid_version")
    assert "Invalid version provided" in str(exc_info.value)

def test_validate_and_set_version_invalid_current_version():
    with pytest.raises(ValueError) as exc_info:
        version_ops.validate_and_set_version("invalid_version", "1.0.1")
    assert "Invalid version provided" in str(exc_info.value)

def test_update_pyproject_version(temp_pyproject):
    original_version, _ = version_ops.read_pyproject_version(temp_pyproject)
    new_version = "1.0.1.dev1"
    version_ops.update_pyproject_version(temp_pyproject, new_version)
    updated_version, _ = version_ops.read_pyproject_version(temp_pyproject)
    assert updated_version == new_version

def test_update_pyproject_version_invalid_structure(temp_pyproject):
    # Modify the pyproject.toml to remove [tool.poetry]
    with open(temp_pyproject, "w", encoding="utf-8") as f:
        f.write("""
[tool.some_other_tool]
name = "test-package"
version = "1.0.0"
""")
    with pytest.raises(SystemExit) as exc_info:
        version_ops.update_pyproject_version(temp_pyproject, "1.0.1.dev1")
    assert "Invalid pyproject.toml structure" in str(exc_info.value)

def test_update_pyproject_version_write_failure(temp_pyproject, mocker):
    # Mock the open function to raise an IOError when writing
    mocker.patch("builtins.open", mocker.mock_open()).side_effect = IOError("Cannot write to file")
    with pytest.raises(SystemExit) as exc_info:
        version_ops.update_pyproject_version(temp_pyproject, "1.0.1.dev1")
    assert "Error writing updated pyproject.toml" in str(exc_info.value)

def test_bump_or_set_version_bump_major(temp_pyproject):
    with mock.patch("soliloquy.version_ops.read_pyproject_version") as mock_read:
        mock_read.return_value = ("1.0.0", {})
        with mock.patch("soliloquy.version_ops.update_pyproject_version") as mock_update:
            version_ops.bump_or_set_version(pyproject_file=temp_pyproject, bump="major")
            mock_update.assert_called_once_with(temp_pyproject, "2.0.0.dev1")

def test_bump_or_set_version_set_version(temp_pyproject):
    with mock.patch("soliloquy.version_ops.read_pyproject_version") as mock_read:
        mock_read.return_value = ("1.0.0", {})
        with mock.patch("soliloquy.version_ops.validate_and_set_version") as mock_validate:
            mock_validate.return_value = "1.2.3"
            with mock.patch("soliloquy.version_ops.update_pyproject_version") as mock_update:
                version_ops.bump_or_set_version(pyproject_file=temp_pyproject, set_ver="1.2.3")
                mock_validate.assert_called_once_with("1.0.0", "1.2.3")
                mock_update.assert_called_once_with(temp_pyproject, "1.2.3")

def test_bump_or_set_version_no_operation(temp_pyproject):
    with pytest.raises(SystemExit) as exc_info:
        version_ops.bump_or_set_version(pyproject_file=temp_pyproject)
    assert "No version operation specified." in str(exc_info.value)

def test_bump_or_set_version_bump_failure():
    with mock.patch("soliloquy.version_ops.read_pyproject_version") as mock_read:
        mock_read.side_effect = Exception("Failed to read version")
        with pytest.raises(SystemExit) as exc_info:
            version_ops.bump_or_set_version(pyproject_file="dummy_path", bump="minor")
        assert "Error reading current version" in str(exc_info.value)

def test_bump_or_set_version_set_failure():
    with mock.patch("soliloquy.version_ops.read_pyproject_version") as mock_read:
        mock_read.return_value = ("1.0.0", {})
        with mock.patch("soliloquy.version_ops.validate_and_set_version") as mock_validate:
            mock_validate.side_effect = ValueError("Cannot set to lower version")
            with pytest.raises(SystemExit) as exc_info:
                version_ops.bump_or_set_version(pyproject_file="dummy_path", set_ver="0.9.0")
            assert "Error: You cannot bump the version downwards" in str(exc_info.value)
