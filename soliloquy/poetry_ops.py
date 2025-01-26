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


def find_pyproject_files(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    default_filename: str = "pyproject.toml"
) -> List[str]:
    """
    Resolve which pyproject.toml file(s) to operate on.

    1. If 'file' is provided, return just that file.
    2. Else if 'directory' is provided:
       - If 'recursive' is True, walk subdirs for default_filename.
       - Otherwise, just look for default_filename in that one directory.
    3. Otherwise, raise an error.
    """
    if file:
        path = os.path.abspath(file)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")
        return [path]

    if directory:
        dir_path = os.path.abspath(directory)
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Directory not found: {dir_path}")

        if recursive:
            matched = []
            for root, dirs, files in os.walk(dir_path):
                if default_filename in files:
                    matched.append(os.path.join(root, default_filename))
            if not matched:
                raise FileNotFoundError(
                    f"No {default_filename} found recursively in {dir_path}"
                )
            return matched
        else:
            single = os.path.join(dir_path, default_filename)
            if not os.path.isfile(single):
                raise FileNotFoundError(f"No {default_filename} in {dir_path}")
            return [single]

    raise ValueError("Must provide either `file` or `directory`.")


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