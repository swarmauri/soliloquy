# tests/test_remote_ops.py

import os
import json
import tempfile
import shutil
import pytest
from unittest import mock
from soliloquy import remote_ops
from tomlkit import parse, dumps

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
def temp_pyproject_git_dep():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file with a Git dependency.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
git_package = { git = "https://github.com/swarmauri/git-package.git", branch = "main", subdirectory = "pkgs/community/git-package" }
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_no_git_dep():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file without any Git dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.25.1"
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_pyproject_multiple_git_deps():
    """
    Pytest fixture to create and clean up a temporary pyproject.toml file with multiple Git dependencies.
    """
    tool_poetry_content = """
[tool.poetry.dependencies]
python = "^3.8"
git_package1 = { git = "https://github.com/swarmauri/git-package1.git", branch = "dev", subdirectory = "pkgs/community/git-package1" }
git_package2 = { git = "https://github.com/swarmauri/git-package2.git", branch = "release", subdirectory = "pkgs/community/git-package2" }
    """
    temp_dir, file_path = create_temp_pyproject(tool_poetry_content)
    yield file_path
    shutil.rmtree(temp_dir)

def test_fetch_remote_pyproject_version_success(mocker):
    # Mock requests.get to return a successful response with a valid pyproject.toml
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = """
[tool.poetry]
name = "remote-package"
version = "2.0.0"
    """
    mocker.patch("requests.get", return_value=mock_response)
    
    version = remote_ops.fetch_remote_pyproject_version(
        git_url="https://github.com/swarmauri/git-package.git",
        branch="main",
        subdirectory="pkgs/community/git-package"
    )
    assert version == "2.0.0"

def test_fetch_remote_pyproject_version_non_github():
    # Attempt to fetch from a non-GitHub URL
    with pytest.raises(ValueError) as exc_info:
        remote_ops.fetch_remote_pyproject_version(
            git_url="https://gitlab.com/swarmauri/git-package.git",
            branch="main",
            subdirectory="pkgs/community/git-package"
        )
    assert "Only GitHub repositories are supported" in str(exc_info.value)

def test_fetch_remote_pyproject_version_http_error(mocker):
    # Mock requests.get to raise an HTTP error
    mock_response = mock.Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mocker.patch("requests.get", return_value=mock_response)
    
    version = remote_ops.fetch_remote_pyproject_version(
        git_url="https://github.com/swarmauri/nonexistent.git",
        branch="main",
        subdirectory=""
    )
    assert version is None

def test_fetch_remote_pyproject_version_missing_version(mocker):
    # Mock requests.get to return a pyproject.toml without a version
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = """
[tool.poetry]
name = "remote-package"
description = "A package without version"
    """
    mocker.patch("requests.get", return_value=mock_response)
    
    version = remote_ops.fetch_remote_pyproject_version(
        git_url="https://github.com/swarmauri/git-package.git",
        branch="main",
        subdirectory=""
    )
    assert version is None

def test_update_pyproject_with_versions_single_git_dep(temp_pyproject_git_dep, mocker, capsys):
    # Mock fetch_remote_pyproject_version to return a specific version
    mocker.patch("soliloquy.remote_ops.fetch_remote_pyproject_version", return_value="2.0.0")
    
    updated_doc = remote_ops.update_pyproject_with_versions(temp_pyproject_git_dep)
    assert updated_doc is not None
    
    # Check that the git dependency has been updated to an inline table with version and optional
    dependencies = updated_doc["tool"]["poetry"]["dependencies"]
    assert "git_package" in dependencies
    dep = dependencies["git_package"]
    assert isinstance(dep, dict)
    assert dep["version"] == "^2.0.0"
    assert dep["optional"] is True
    
    # Ensure that the function printed the expected output
    captured = capsys.readouterr()
    assert "Updating dependency 'git_package':" in captured.out
    assert "Fetched version: 2.0.0" in captured.out

def test_update_pyproject_with_versions_single_git_dep_fetch_fail(temp_pyproject_git_dep, mocker, capsys):
    # Mock fetch_remote_pyproject_version to return None
    mocker.patch("soliloquy.remote_ops.fetch_remote_pyproject_version", return_value=None)
    
    updated_doc = remote_ops.update_pyproject_with_versions(temp_pyproject_git_dep)
    assert updated_doc is not None
    
    # Check that the git dependency has been marked as optional without a version
    dependencies = updated_doc["tool"]["poetry"]["dependencies"]
    assert "git_package" in dependencies
    dep = dependencies["git_package"]
    assert isinstance(dep, dict)
    assert dep.get("version") is None
    assert dep["optional"] is True
    
    # Ensure that the function printed the expected output
    captured = capsys.readouterr()
    assert "Could not fetch remote version for 'git_package'. Marking as optional." in captured.out

def test_update_pyproject_with_versions_no_git_dep(temp_pyproject_no_git_dep, mocker, capsys):
    # Ensure that no changes are made when there are no Git dependencies
    updated_doc = remote_ops.update_pyproject_with_versions(temp_pyproject_no_git_dep)
    assert updated_doc is not None
    
    # Check that dependencies remain unchanged
    dependencies = updated_doc["tool"]["poetry"]["dependencies"]
    assert "requests" in dependencies
    assert dependencies["requests"] == "^2.25.1"
    
    # Ensure that the function printed the expected output
    captured = capsys.readouterr()
    assert "Updating dependency" not in captured.out

def test_update_pyproject_with_versions_multiple_git_deps(temp_pyproject_multiple_git_deps, mocker, capsys):
    # Mock fetch_remote_pyproject_version to return specific versions based on URL
    def mock_fetch(git_url, branch, subdirectory):
        if git_url == "https://github.com/swarmauri/git-package1.git":
            return "1.2.3"
        elif git_url == "https://github.com/swarmauri/git-package2.git":
            return "4.5.6"
        return None
    
    mocker.patch("soliloquy.remote_ops.fetch_remote_pyproject_version", side_effect=mock_fetch)
    
    updated_doc = remote_ops.update_pyproject_with_versions(temp_pyproject_multiple_git_deps)
    assert updated_doc is not None
    
    # Check git_package1
    dependencies = updated_doc["tool"]["poetry"]["dependencies"]
    assert "git_package1" in dependencies
    dep1 = dependencies["git_package1"]
    assert dep1["version"] == "^1.2.3"
    assert dep1["optional"] is True
    
    # Check git_package2
    assert "git_package2" in dependencies
    dep2 = dependencies["git_package2"]
    assert dep2["version"] == "^4.5.6"
    assert dep2["optional"] is True
    
    # Ensure that the function printed the expected output
    captured = capsys.readouterr()
    assert "Updating dependency 'git_package1':" in captured.out
    assert "Fetched version: 1.2.3" in captured.out
    assert "Updating dependency 'git_package2':" in captured.out
    assert "Fetched version: 4.5.6" in captured.out

def test_update_pyproject_with_versions_invalid_structure(temp_pyproject_no_git_dep, capsys):
    # Modify the pyproject.toml to remove [tool.poetry]
    with open(temp_pyproject_no_git_dep, "w", encoding="utf-8") as f:
        f.write("""
[tool.some_other_tool]
name = "test-package"
version = "1.0.0"
""")
    
    updated_doc = remote_ops.update_pyproject_with_versions(temp_pyproject_no_git_dep)
    assert updated_doc is None
    
    # Ensure that the function printed the expected error message
    captured = capsys.readouterr()
    assert "Error: Invalid pyproject.toml structure" in captured.out

def test_update_and_write_pyproject_success(temp_pyproject_git_dep, mocker, capsys):
    # Mock update_pyproject_with_versions to return a modified doc
    mock_doc = parse("""
[tool.poetry.dependencies]
python = "^3.8"
git_package = { version = "^2.0.0", optional = true }
""")
    mocker.patch("soliloquy.remote_ops.update_pyproject_with_versions", return_value=mock_doc)
    
    # Mock open to write the file without errors
    mocker.patch("builtins.open", mock.mock_open())
    
    success = remote_ops.update_and_write_pyproject(temp_pyproject_git_dep, output_file_path="updated_pyproject.toml")
    assert success == True
    
    # Ensure that the function printed the expected output
    captured = capsys.readouterr()
    assert "Updated pyproject.toml written to updated_pyproject.toml" in captured.out

def test_update_and_write_pyproject_overwrite(temp_pyproject_git_dep, mocker, capsys):
    # Mock update_pyproject_with_versions to return a modified doc
    mock_doc = parse("""
[tool.poetry.dependencies]
python = "^3.8"
git_package = { version = "^2.0.0", optional = true }
""")
    mocker.patch("soliloquy.remote_ops.update_pyproject_with_versions", return_value=mock_doc)
    
    # Mock open to write the file without errors
    mocker.patch("builtins.open", mock.mock_open())
    
    success = remote_ops.update_and_write_pyproject(temp_pyproject_git_dep)
    assert success == True
    
    # Ensure that the function wrote to the input file path
    captured = capsys.readouterr()
    assert f"Updated pyproject.toml written to {temp_pyproject_git_dep}" in captured.out

def test_update_and_write_pyproject_write_failure(temp_pyproject_git_dep, mocker, capsys):
    # Mock update_pyproject_with_versions to return a modified doc
    mock_doc = parse("""
[tool.poetry.dependencies]
python = "^3.8"
git_package = { version = "^2.0.0", optional = true }
""")
    mocker.patch("soliloquy.remote_ops.update_pyproject_with_versions", return_value=mock_doc)
    
    # Mock open to raise an IOError when writing
    mocker.patch("builtins.open", mock.mock_open()).side_effect = IOError("Cannot write to file")
    
    success = remote_ops.update_and_write_pyproject(temp_pyproject_git_dep, output_file_path="updated_pyproject.toml")
    assert success == False
    
    # Ensure that the function printed the expected error message
    captured = capsys.readouterr()
    assert "Error writing updated pyproject.toml" in captured.out

def test_update_and_write_pyproject_update_failure(temp_pyproject_git_dep, mocker, capsys):
    # Mock update_pyproject_with_versions to return None indicating failure
    mocker.patch("soliloquy.remote_ops.update_pyproject_with_versions", return_value=None)
    
    success = remote_ops.update_and_write_pyproject(temp_pyproject_git_dep, output_file_path="updated_pyproject.toml")
    assert success == False
    
    # Ensure that the function printed the expected error message
    captured = capsys.readouterr()
    assert "Failed to update the pyproject.toml document." in captured.out
