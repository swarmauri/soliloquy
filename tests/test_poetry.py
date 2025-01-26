# tests/test_poetry_ops.py

import os
import tempfile
import shutil
import pytest
from unittest import mock
from soliloquy import poetry_ops
from soliloquy.pyproject_ops import find_pyproject_files
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
def temp_pyproject_basic():
    """
    Pytest fixture to create and clean up a basic temporary pyproject.toml file.
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
def temp_pyproject_with_path_deps():
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
def temp_pyproject_with_git_deps():
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

def test_run_command_success(mocker):
    # Mock subprocess.run to simulate a successful command
    mock_subprocess = mocker.patch('soliloquy.poetry_ops.subprocess.run')
    mock_subprocess.return_value = mock.Mock(stdout="Success", stderr="", returncode=0)
    
    output = poetry_ops.run_command(["echo", "Success"])
    mock_subprocess.assert_called_once_with(
        ["echo", "Success"],
        cwd=None,
        text=True,
        capture_output=True,
        shell=False,
        check=True
    )
    assert output == "Success"

def test_run_command_failure(mocker, capsys):
    # Mock subprocess.run to simulate a failed command
    mock_subprocess = mocker.patch('soliloquy.poetry_ops.subprocess.run')
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["false"],
        stderr="Error occurred"
    )
    
    with pytest.raises(SystemExit) as exc_info:
        poetry_ops.run_command(["false"])
    
    captured = capsys.readouterr()
    assert "Error running command: Error occurred" in captured.err
    assert exc_info.value.code == 1

def test_poetry_lock_success(mocker):
    # Mock run_command to simulate 'poetry lock' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_lock("/path/to/project")
    
    mock_run.assert_called_once_with(["poetry", "lock"], cwd="/path/to/project")

def test_poetry_install_success(mocker):
    # Mock run_command to simulate 'poetry install' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_install(
        location="/path/to/project",
        extras="full",
        with_dev=True,
        all_extras=False
    )
    
    mock_run.assert_called_once_with(
        ["poetry", "install", "--no-cache", "-vv", "--extras", "full", "--with", "dev"],
        cwd="/path/to/project"
    )

def test_poetry_install_all_extras(mocker):
    # Mock run_command to simulate 'poetry install --all-extras' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_install(
        location="/path/to/project",
        extras=None,
        with_dev=False,
        all_extras=True
    )
    
    mock_run.assert_called_once_with(
        ["poetry", "install", "--no-cache", "-vv", "--all-extras"],
        cwd="/path/to/project"
    )

def test_extract_path_dependencies(temp_pyproject_with_path_deps):
    paths = poetry_ops.extract_path_dependencies(temp_pyproject_with_path_deps)
    assert len(paths) == 2
    assert "./libs/local_package" in paths
    assert "../another_local" in paths

def test_extract_path_dependencies_no_path_deps(temp_pyproject_basic):
    paths = poetry_ops.extract_path_dependencies(temp_pyproject_basic)
    assert len(paths) == 0

def test_extract_path_dependencies_file_not_found(mocker, capsys):
    # Mock opening a non-existent file
    mocker.patch("builtins.open", mock.mock_open()).side_effect=FileNotFoundError("File not found")
    
    with pytest.raises(SystemExit) as exc_info:
        poetry_ops.extract_path_dependencies("nonexistent/pyproject.toml")
    
    captured = capsys.readouterr()
    assert "Error reading nonexistent/pyproject.toml: File not found" in captured.err
    assert exc_info.value.code == 1

def test_recursive_build_success(mocker, temp_pyproject_with_path_deps):
    # Mock extract_path_dependencies to return specific paths
    mocker.patch('soliloquy.poetry_ops.extract_path_dependencies', return_value=["./libs/local_package", "../another_local"])
    
    # Mock run_command to simulate 'poetry build' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.recursive_build("/path/to/project")
    
    expected_calls = [
        mock.call(["poetry", "build"], cwd="/path/to/project/libs/local_package"),
        mock.call(["poetry", "build"], cwd="/path/to/another_local")
    ]
    mock_run.assert_has_calls(expected_calls, any_order=True)
    assert mock_run.call_count == 2

def test_recursive_build_invalid_package(mocker, temp_pyproject_with_path_deps, capsys):
    # Mock extract_path_dependencies to return a path that doesn't have pyproject.toml
    mocker.patch('soliloquy.poetry_ops.extract_path_dependencies', return_value=["./libs/nonexistent_package"])
    
    # Mock run_command to simulate 'poetry build' not being called
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.recursive_build("/path/to/project")
    
    # Ensure run_command was not called since package is invalid
    mock_run.assert_not_called()
    
    captured = capsys.readouterr()
    assert "Skipping /path/to/project/libs/nonexistent_package: 'pyproject.toml' not found." in captured.out

def test_run_pytests_single_worker(mocker):
    # Mock run_command to simulate 'poetry run pytest' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.run_pytests(test_directory="/path/to/tests", num_workers=1)
    
    mock_run.assert_called_once_with(
        ["poetry", "run", "pytest"],
        cwd="/path/to/tests"
    )

def test_run_pytests_multiple_workers(mocker):
    # Mock run_command to simulate 'poetry run pytest -n 4' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.run_pytests(test_directory="/path/to/tests", num_workers=4)
    
    mock_run.assert_called_once_with(
        ["poetry", "run", "pytest", "-n", "4"],
        cwd="/path/to/tests"
    )

def test_run_pytests_failure(mocker, capsys):
    # Mock run_command to simulate pytest failure
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["pytest"], stderr="Test failed")
    
    with pytest.raises(SystemExit) as exc_info:
        poetry_ops.run_pytests(test_directory="/path/to/tests", num_workers=1)
    
    captured = capsys.readouterr()
    assert "Error running command: Test failed" in captured.err
    assert exc_info.value.code == 1

def test_poetry_ruff_lint_no_fix(mocker):
    # Mock run_command to simulate 'poetry run ruff check' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_ruff_lint(directory="/path/to/code", fix=False)
    
    mock_run.assert_called_once_with(
        ["poetry", "run", "ruff", "check", "/path/to/code"]
    )

def test_poetry_ruff_lint_with_fix(mocker):
    # Mock run_command to simulate 'poetry run ruff check --fix' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_ruff_lint(directory="/path/to/code", fix=True)
    
    mock_run.assert_called_once_with(
        ["poetry", "run", "ruff", "check", "/path/to/code", "--fix"]
    )

def test_build_monorepo_success(mocker, temp_pyproject_with_git_deps):
    # Mock extract_path_dependencies and extract_git_dependencies
    mocker.patch('soliloquy.poetry_ops.extract_path_dependencies', return_value=[])
    mocker.patch('soliloquy.poetry_ops.extract_git_dependencies', return_value={
        "git_package": {"subdirectory": "pkgs/community/git-package"},
        "another_git": {"subdirectory": "pkgs/community/another-git"}
    })
    
    # Mock run_command to simulate 'poetry build' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.build_monorepo(file="/path/to/monorepo/pyproject.toml")
    
    expected_calls = [
        mock.call(["poetry", "build"], cwd="/path/to/monorepo/pkgs/community/git-package"),
        mock.call(["poetry", "build"], cwd="/path/to/monorepo/pkgs/community/another-git")
    ]
    mock_run.assert_has_calls(expected_calls, any_order=True)
    assert mock_run.call_count == 2

def test_build_monorepo_no_git_deps(mocker, temp_pyproject_basic, capsys):
    # Mock extract_path_dependencies and extract_git_dependencies to return empty
    mocker.patch('soliloquy.poetry_ops.extract_path_dependencies', return_value=[])
    mocker.patch('soliloquy.poetry_ops.extract_git_dependencies', return_value={})
    
    # Mock run_command to simulate 'poetry build' not being called
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.build_monorepo(file="/path/to/monorepo/pyproject.toml")
    
    mock_run.assert_not_called()
    
    captured = capsys.readouterr()
    assert "No Git dependencies found in aggregator." in captured.out
    assert "Monorepo build completed." in captured.out

def test_build_monorepo_invalid_file(mocker, capsys):
    # Attempt to build with a non-existent file
    with pytest.raises(FileNotFoundError) as exc_info:
        poetry_ops.build_monorepo(file="nonexistent/pyproject.toml")
    
    assert "Monorepo file not found: nonexistent/pyproject.toml" in str(exc_info.value)

def test_build_monorepo_build_failure(mocker, temp_pyproject_with_git_deps, capsys):
    # Mock extract_path_dependencies and extract_git_dependencies
    mocker.patch('soliloquy.poetry_ops.extract_path_dependencies', return_value=[])
    mocker.patch('soliloquy.poetry_ops.extract_git_dependencies', return_value={
        "git_package": {"subdirectory": "pkgs/community/git-package"},
    })
    
    # Mock run_command to simulate 'poetry build' failure
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["poetry", "build"], stderr="Build failed")
    
    poetry_ops.build_monorepo(file="/path/to/monorepo/pyproject.toml")
    
    mock_run.assert_called_once_with(
        ["poetry", "build"],
        cwd="/path/to/monorepo/pkgs/community/git-package"
    )
    
    captured = capsys.readouterr()
    assert "Failed to build Git dependency /path/to/monorepo/pkgs/community/git-package: Build failed" in captured.err
    # Since poetry_ops.build_monorepo does not exit on failure, adjust if necessary

def test_poetry_publish_success(mocker, temp_pyproject_basic):
    # Mock find_pyproject_files to return a list of pyproject.toml files
    mocker.patch('soliloquy.pyproject_ops.find_pyproject_files', return_value=["/path/to/project/pyproject.toml"])
    
    # Mock run_command to simulate 'poetry build' and 'poetry publish' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_publish(
        file="/path/to/project/pyproject.toml",
        directory=None,
        recursive=False,
        username="user",
        password="pass"
    )
    
    expected_calls = [
        mock.call(["poetry", "build"], cwd="/path/to/project"),
        mock.call(["poetry", "publish", "--username", "user", "--password", "pass"], cwd="/path/to/project")
    ]
    mock_run.assert_has_calls(expected_calls)
    assert mock_run.call_count == 2

def test_poetry_publish_multiple_projects(mocker, temp_pyproject_basic):
    # Mock find_pyproject_files to return multiple pyproject.toml files
    mocker.patch('soliloquy.pyproject_ops.find_pyproject_files', return_value=[
        "/path/to/project1/pyproject.toml",
        "/path/to/project2/pyproject.toml"
    ])
    
    # Mock run_command to simulate 'poetry build' and 'poetry publish' success
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    
    poetry_ops.poetry_publish(
        directory="/path/to/projects",
        recursive=True,
        username="user",
        password="pass"
    )
    
    expected_calls = [
        mock.call(["poetry", "build"], cwd="/path/to/project1"),
        mock.call(["poetry", "publish", "--username", "user", "--password", "pass"], cwd="/path/to/project1"),
        mock.call(["poetry", "build"], cwd="/path/to/project2"),
        mock.call(["poetry", "publish", "--username", "user", "--password", "pass"], cwd="/path/to/project2")
    ]
    mock_run.assert_has_calls(expected_calls, any_order=False)
    assert mock_run.call_count == 4

def test_poetry_publish_build_failure(mocker, temp_pyproject_basic, capsys):
    # Mock find_pyproject_files to return a list of pyproject.toml files
    mocker.patch('soliloquy.pyproject_ops.find_pyproject_files', return_value=["/path/to/project/pyproject.toml"])
    
    # Mock run_command to simulate 'poetry build' failure
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    mock_run.side_effect = [
        subprocess.CalledProcessError(returncode=1, cmd=["poetry", "build"], stderr="Build failed"),
        # 'poetry publish' won't be called due to build failure
    ]
    
    with pytest.raises(SystemExit) as exc_info:
        poetry_ops.poetry_publish(
            file="/path/to/project/pyproject.toml",
            directory=None,
            recursive=False,
            username="user",
            password="pass"
        )
    
    mock_run.assert_called_once_with(["poetry", "build"], cwd="/path/to/project")
    captured = capsys.readouterr()
    assert "Failed to build package in /path/to/project: Build failed" in captured.err
    assert exc_info.value.code == 1

def test_poetry_publish_publish_failure(mocker, temp_pyproject_basic, capsys):
    # Mock find_pyproject_files to return a list of pyproject.toml files
    mocker.patch('soliloquy.pyproject_ops.find_pyproject_files', return_value=["/path/to/project/pyproject.toml"])
    
    # Mock run_command to simulate 'poetry build' success and 'poetry publish' failure
    mock_run = mocker.patch('soliloquy.poetry_ops.run_command')
    mock_run.side_effect = [
        mock.Mock(stdout="Build succeeded", returncode=0),
        subprocess.CalledProcessError(returncode=1, cmd=["poetry", "publish"], stderr="Publish failed")
    ]
    
    with pytest.raises(SystemExit) as exc_info:
        poetry_ops.poetry_publish(
            file="/path/to/project/pyproject.toml",
            directory=None,
            recursive=False,
            username="user",
            password="pass"
        )
    
    expected_calls = [
        mock.call(["poetry", "build"], cwd="/path/to/project"),
        mock.call(["poetry", "publish", "--username", "user", "--password", "pass"], cwd="/path/to/project")
    ]
    mock_run.assert_has_calls(expected_calls)
    assert mock_run.call_count == 2
    
    captured = capsys.readouterr()
    assert "Failed to publish package in /path/to/project: Publish failed" in captured.err
    assert exc_info.value.code == 1

def test_find_pyproject_files_with_file():
    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "pyproject.toml")
    with open(file_path, "w") as f:
        f.write("[tool.poetry]\nname = 'test'\nversion = '1.0.0'\n")
    
    try:
        result = find_pyproject_files(file=file_path)
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
        result = find_pyproject_files(directory=temp_dir, recursive=False)
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
        result = find_pyproject_files(directory=temp_dir, recursive=True)
        expected = [os.path.abspath(file1), os.path.abspath(file2)]
        assert set(result) == set(expected)
    finally:
        shutil.rmtree(temp_dir)

def test_find_pyproject_files_missing_file():
    # Attempt to find a non-existent file
    with pytest.raises(FileNotFoundError):
        find_pyproject_files(file="nonexistent/pyproject.toml")

def test_find_pyproject_files_missing_directory():
    # Attempt to find in a non-existent directory
    with pytest.raises(NotADirectoryError):
        find_pyproject_files(directory="nonexistent_dir")

def test_find_pyproject_files_no_inputs():
    # Attempt to find without providing file or directory
    with pytest.raises(ValueError):
        find_pyproject_files()

def test_find_pyproject_files_recursive_no_pyproject():
    # Create a temporary directory without any pyproject.toml files
    temp_dir = tempfile.mkdtemp()
    try:
        with pytest.raises(FileNotFoundError):
            find_pyproject_files(directory=temp_dir, recursive=True)
    finally:
        shutil.rmtree(temp_dir)
