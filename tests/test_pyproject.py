# tests/test_pyproject_ops.py

import os
import json
import tempfile
import shutil
import pytest
from unittest import mock
from soliloquy import pyproject_ops
from tomlkit import parse, dumps, table

# Helper function to create a temporary pyproject.toml file
def create_temp_pyproject(tool_poetry_content, extra_content=""):
    content = f"""
[tool.poetry]
name = "test-package"
version = "1.0.0"
description = "A test package"
authors = ["Test Author <test@example.com>"]

{tool_poetry_content}

{extra_content}
"""
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return temp_dir, file_path

@pytest.fixture
def temp_pyproject_path_dep():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file with path dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
local_package = { path = "./libs/local_package" }
another_local = { path = "../another_local" }
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_no_path_dep():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file without path dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.25.1"
flask = "^1.1.2"
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_git_deps():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file with Git dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
git_package = { git = "https://github.com/swarmauri/git-package.git", branch = "main", subdirectory = "pkgs/community/git-package" }
another_git = { git = "https://github.com/swarmauri/another-git.git", branch = "develop", subdirectory = "pkgs/community/another-git" }
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_no_git_deps():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file without Git dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.25.1"
flask = "^1.1.2"
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_invalid_structure():
    """
    Pytest fixture to create and clean up a temporary invalid pyproject.toml file.
    """
    content = """
[tool.some_other_tool]
name = "invalid-package"
version = "1.0.0"
    """
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path
    shutil.rmtree(temp_dir)

def test_extract_path_dependencies_with_paths(temp_pyproject_path_dep):
    paths = pyproject_ops.extract_path_dependencies(temp_pyproject_path_dep)
    assert len(paths) == 2
    assert "./libs/local_package" in paths
    assert "../another_local" in paths

def test_extract_path_dependencies_no_paths(temp_pyproject_no_path_dep):
    paths = pyproject_ops.extract_path_dependencies(temp_pyproject_no_path_dep)
    assert len(paths) == 0

def test_extract_git_dependencies_with_git_deps(temp_pyproject_git_deps):
    git_deps = pyproject_ops.extract_git_dependencies(temp_pyproject_git_deps)
    assert len(git_deps) == 2
    assert "git_package" in git_deps
    assert git_deps["git_package"]["git"] == "https://github.com/swarmauri/git-package.git"
    assert "another_git" in git_deps
    assert git_deps["another_git"]["branch"] == "develop"

def test_extract_git_dependencies_no_git_deps(temp_pyproject_no_git_deps):
    git_deps = pyproject_ops.extract_git_dependencies(temp_pyproject_no_git_deps)
    assert len(git_deps) == 0

def test_extract_git_dependencies_invalid_pyproject(temp_pyproject_invalid_structure, capsys):
    git_deps = pyproject_ops.extract_git_dependencies(temp_pyproject_invalid_structure)
    assert len(git_deps) == 0
    captured = capsys.readouterr()
    assert "Version key not found" not in captured.out  # Since it's a different structure

def test_update_dependency_versions_success(temp_pyproject_path_dep, mocker, capsys):
    # Mock the dependency's own pyproject.toml existence and updating
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("builtins.open", mock.mock_open(read_data="""
[tool.poetry]
name = "local_package"
version = "0.1.0"
    """))
    # Mock writing to the dependency's pyproject.toml
    mock_write = mock.mock_open()
    mocker.patch("builtins.open", mock_write)

    # Call the update function
    pyproject_ops.update_dependency_versions(temp_pyproject_path_dep, "1.1.0")

    # Verify that the parent pyproject.toml was read and written
    assert mock_write.call_count >= 2  # One read, one write for parent, and writes for dependencies

    # Verify that the dependency's version was updated
    handle = mock_write()
    handle.write.assert_any_call('version = "1.1.0"\n')

    # Verify that the parent pyproject.toml was updated with new versions
    captured = capsys.readouterr()
    assert "Updated ./libs/local_package/pyproject.toml to version 1.1.0" in captured.out
    assert "Updated dependency versions in " in captured.out

def test_update_dependency_versions_no_dependency_pyproject(temp_pyproject_path_dep, mocker, capsys):
    # Mock the dependency's own pyproject.toml does not exist
    def isfile_side_effect(path):
        if "libs/local_package/pyproject.toml" in path or "../another_local/pyproject.toml" in path:
            return False
        return True

    mocker.patch("os.path.isfile", side_effect=isfile_side_effect)
    # Mock writing to the parent pyproject.toml
    mock_write = mock.mock_open()
    mocker.patch("builtins.open", mock_write)

    # Call the update function
    pyproject_ops.update_dependency_versions(temp_pyproject_path_dep, "1.1.0")

    # Verify that only the parent pyproject.toml was written
    assert mock_write.call_count == 1  # Only parent written

    # Verify that dependencies were updated
    handle = mock_write()
    handle.write.assert_called()  # Called at least once

    # Verify printed output
    captured = capsys.readouterr()
    assert "Could not fetch remote version for 'local_package'. Marking as optional." in captured.out
    assert "Could not fetch remote version for 'another_local'. Marking as optional." in captured.out
    assert "Updated dependency versions in " in captured.out

def test_update_dependency_versions_invalid_pyproject(temp_pyproject_invalid_structure, capsys):
    # Attempt to update an invalid pyproject.toml structure
    updated_doc = pyproject_ops.update_dependency_versions(temp_pyproject_invalid_structure, "1.1.0")
    assert updated_doc is None

    # Check that an error message was printed
    captured = capsys.readouterr()
    assert "Error: Invalid pyproject.toml structure" in captured.out

def test_update_dependency_versions_write_failure(temp_pyproject_path_dep, mocker, capsys):
    # Mock the dependency's own pyproject.toml existence and updating
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("builtins.open", mock.mock_open(read_data="""
[tool.poetry]
name = "local_package"
version = "0.1.0"
    """))
    # Mock writing to the dependency's pyproject.toml to raise an IOError
    mocker.patch("builtins.open", mock.mock_open())
    mock_write = mock.mock_open()
    mocker.patch("builtins.open", mock_write).side_effect = IOError("Cannot write to file")

    # Call the update function
    with pytest.raises(SystemExit) as exc_info:
        pyproject_ops.update_dependency_versions(temp_pyproject_path_dep, "1.1.0")
    captured = capsys.readouterr()
    assert "Error writing updated file" in captured.out
    assert exc_info.value.code == 1

def test_find_pyproject_files_with_file():
    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w") as f:
        f.write("[tool.poetry]\nname = 'test'\nversion = '1.0.0'\n")
    
    try:
        result = pyproject_ops.find_pyproject_files(file=file_path)
        assert result == [os.path.abspath(file_path)]
    finally:
        shutil.rmtree(temp_dir)

def test_find_pyproject_files_with_directory_non_recursive():
    # Create a temporary directory with one pyproject.toml
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w") as f:
        f.write("[tool.poetry]\nname = 'test'\nversion = '1.0.0'\n")
    
    try:
        result = pyproject_ops.find_pyproject_files(directory=temp_dir, recursive=False)
        assert result == [os.path.abspath(file_path)]
    finally:
        shutil.rmtree(temp_dir)

def test_find_pyproject_files_with_directory_recursive():
    # Create a temporary directory with multiple pyproject.toml files
    temp_dir = tempfile.mkdtemp()
    subdir1 = os.path.join(temp_dir, "subdir1")
    subdir2 = os.path.join(temp_dir, "subdir2")
    os.makedirs(subdir1)
    os.makedirs(subdir2)
    file1 = os.path.join(subdir1, "pyproject.toml")
    file2 = os.path.join(subdir2, "pyproject.toml")
    with open(file1, "w") as f:
        f.write("[tool.poetry]\nname = 'test1'\nversion = '1.0.0'\n")
    with open(file2, "w") as f:
        f.write("[tool.poetry]\nname = 'test2'\nversion = '2.0.0'\n")
    
    try:
        result = pyproject_ops.find_pyproject_files(directory=temp_dir, recursive=True)
        expected = [os.path.abspath(file1), os.path.abspath(file2)]
        assert set(result) == set(expected)
    finally:
        shutil.rmtree(temp_dir)

def test_find_pyproject_files_missing_file():
    # Attempt to find a non-existent file
    with pytest.raises(FileNotFoundError):
        pyproject_ops.find_pyproject_files(file="nonexistent/pyproject.toml")

def test_find_pyproject_files_missing_directory():
    # Attempt to find in a non-existent directory
    with pytest.raises(NotADirectoryError):
        pyproject_ops.find_pyproject_files(directory="nonexistent_dir")

def test_find_pyproject_files_no_inputs():
    # Attempt to find without providing file or directory
    with pytest.raises(ValueError):
        pyproject_ops.find_pyproject_files()

def test_find_pyproject_files_recursive_no_pyproject():
    # Create a temporary directory without any pyproject.toml files
    temp_dir = tempfile.mkdtemp()
    try:
        with pytest.raises(FileNotFoundError):
            pyproject_ops.find_pyproject_files(directory=temp_dir, recursive=True)
    finally:
        shutil.rmtree(temp_dir)
