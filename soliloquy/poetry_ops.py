#!/usr/bin/env python3
"""
poetry_ops.py

Key changes:
  - Removed install_poetry()
  - run_command now uses shell=False and an array of arguments
  - If reading/writing pyproject, switch to tomlkit (if needed)
"""
from typing import List
import os
import subprocess
import sys
import tomlkit
from .pyproject_ops import extract_path_dependencies, extract_git_dependencies, find_pyproject_files

def run_command(command_args, cwd=None):
    """
    Run a shell command (as a list of args) with shell=False,
    capturing output. Raises CalledProcessError on failure.
    """
    try:
        result = subprocess.run(
            command_args,
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False,
            check=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr}", file=sys.stderr)
        sys.exit(e.returncode)


def poetry_lock(location):
    """
    Run 'poetry lock' in the specified location (directory).
    """
    print(f"Generating poetry.lock in {location}...")
    run_command(["poetry", "lock"], cwd=location)


def poetry_install(location, extras=None, with_dev=False, all_extras=False):
    """
    Run 'poetry install' in the specified location.
    """
    print(f"Installing dependencies in {location}...")
    command = ["poetry", "install", "--no-cache", "-vv"]
    if all_extras:
        command.append("--all-extras")
    elif extras:
        command.extend(["--extras", extras])
    if with_dev:
        command.extend(["--with", "dev"])
    run_command(command, cwd=location)


def extract_path_dependencies(pyproject_path):
    """
    Example reading with tomlkit instead of toml.
    """
    print(f"Extracting path dependencies from {pyproject_path}...")
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)

    deps = doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
    path_deps = [
        v["path"]
        for v in deps.values()
        if isinstance(v, dict) and "path" in v
    ]
    return path_deps


def recursive_build(location):
    """
    Recursively build packages based on path dependencies extracted from a pyproject.toml.
    """
    pyproject_path = os.path.join(location, "pyproject.toml")
    if not os.path.isfile(pyproject_path):
        print(f"No pyproject.toml found in {location}", file=sys.stderr)
        return

    dependencies = extract_path_dependencies(pyproject_path)
    print("Building specified packages...")
    base_dir = os.path.dirname(pyproject_path)

    for package_path in dependencies:
        full_path = os.path.join(base_dir, package_path)
        pyproject_file = os.path.join(full_path, "pyproject.toml")
        if os.path.isdir(full_path) and os.path.isfile(pyproject_file):
            print(f"Building package: {full_path}")
            run_command(["poetry", "build"], cwd=full_path)
        else:
            print(f"Skipping {full_path}: not a valid package directory")


def run_pytests(test_directory=".", num_workers=1):
    """
    Run pytest in the specified directory.
    """
    command = ["poertry", "run", "pytest"]
    if num_workers > 1:
        command.extend(["-n", str(num_workers)])
    print(f"Running tests in '{test_directory}' with command: {' '.join(command)}")
    run_command(command, cwd=test_directory)


def poetry_ruff_lint(directory=".", fix=False):
    """
    Runs Ruff lint checks in the specified directory.
    If fix=True, also pass --fix to autofix issues.
    
    :param directory: The directory to lint (defaults to '.')
    :param fix: Whether to run with --fix (autofixing) enabled.
    """
    # Construct the base command: 'poetry run ruff check <dir>'
    command = ["poetry", "run", "ruff", "check", directory]
    if fix:
        command.append("--fix")

    print(f"Running Ruff on '{directory}' (fix={fix})...")
    run_command(command)


def build_monorepo(file: str):
    """
    Build a monorepo aggregator pyproject.toml that has 'package-mode=false'
    in [tool.poetry], plus any local path and Git dependencies.

    :param file: Path to the monorepo aggregator pyproject.toml.
    """
    if not file or not os.path.isfile(file):
        raise FileNotFoundError(f"Monorepo file not found: {file}")

    print(f"Building monorepo aggregator from {file}")

    with open(file, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())

    tool_poetry = doc.get("tool", {}).get("poetry", {})
    pkg_mode = tool_poetry.get("package-mode", True)  # default to True
    if pkg_mode is not False:
        print("Warning: This file doesn't specify package-mode=false. Continuing anyway...")

    # Base directory of the monorepo
    base_dir = os.path.dirname(os.path.abspath(file))

    # Step 1: Build path dependencies
    path_deps = extract_path_dependencies(file)
    print(f"Found {len(path_deps)} path dependencies in aggregator {file}.")

    for dep in path_deps:
        full_path = os.path.join(base_dir, dep)
        sub_pyproj = os.path.join(full_path, "pyproject.toml")
        if os.path.isdir(full_path) and os.path.isfile(sub_pyproj):
            print(f"Building local path dependency: {full_path}")
            try:
                run_command(["poetry", "build"], cwd=full_path)
            except Exception as e:
                print(f"Failed to build path dependency {full_path}: {e}", file=sys.stderr)
        else:
            print(f"Skipping {full_path}: not a valid local package directory.")

    # Step 2: Build Git dependencies
    git_deps = extract_git_dependencies(file)
    if git_deps:
        print(f"Found {len(git_deps)} Git dependencies in aggregator {file}.")

        list_of_subdirs = [git_deps[pkg].get('subdirectory', '.') for pkg in git_deps]
        for subdir in list_of_subdirs:
            full_subdir_path = os.path.join(base_dir, subdir)
            sub_pyproj = os.path.join(full_subdir_path, "pyproject.toml")
            if os.path.isdir(full_subdir_path) and os.path.isfile(sub_pyproj):
                print(f"Building Git dependency package: {full_subdir_path}")
                try:
                    run_command(["poetry", "build"], cwd=full_subdir_path)
                except Exception as e:
                    print(f"Failed to build Git dependency {full_subdir_path}: {e}", file=sys.stderr)
            else:
                print(f"Skipping Git dependency subdir {full_subdir_path}: not a valid package directory.")
    else:
        print("No Git dependencies found in aggregator.")

    print("Monorepo build completed.")

def poetry_publish(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    username: str = None,
    password: str = None
):
    """
    Builds and publishes packages to PyPI (or another configured repository).

    You can specify one of:
      - file=<path to pyproject.toml>
      - directory=<path to directory containing pyproject.toml>
      - directory=<path> + recursive=True to walk subdirectories

    :param file: Explicit path to a pyproject.toml file.
    :param directory: Path to a directory that has (or contains) a pyproject.toml.
    :param recursive: If True, search subdirectories for pyproject.toml files.
    :param username: PyPI username (optional). If not provided, rely on Poetry config or interactive prompt.
    :param password: PyPI password (optional).
    """
    try:
        pyproject_files = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"Error discovering pyproject files: {e}", file=sys.stderr)
        sys.exit(1)

    for pyproj in pyproject_files:
        project_dir = os.path.dirname(pyproj)
        print(f"Publishing package from {project_dir} ...")

        # 1. Build the package
        try:
            run_command(["poetry", "build"], cwd=project_dir)
        except Exception as e:
            print(f"Failed to build package in {project_dir}: {e}", file=sys.stderr)
            sys.exit(1)

        # 2. Publish the package
        publish_cmd = ["poetry", "publish"]
        # If you want verbose output, you can add ["-vv"] or similar
        if username and password:
            publish_cmd.extend(["--username", username, "--password", password])
        # If you have a custom repository name, you can also add --repository <repo>

        try:
            run_command(publish_cmd, cwd=project_dir)
        except Exception as e:
            print(f"Failed to publish package in {project_dir}: {e}", file=sys.stderr)
            sys.exit(1)