#!/usr/bin/env python3
"""
pyproject_ops.py

- Now uses tomlkit instead of toml
"""

from typing import List
import os
import sys
import tomlkit

def extract_path_dependencies(pyproject_path):
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)

    dependencies = doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
    path_deps = []
    for val in dependencies.values():
        if isinstance(val, dict) and "path" in val:
            path_deps.append(val["path"])
    return path_deps

def extract_git_dependencies(pyproject_path):
    """
    Extract Git-based dependencies from a pyproject.toml file.

    Looks for dependencies in [tool.poetry.dependencies] that are dictionaries containing a "git" key.

    Args:
        pyproject_path (str): Path to the pyproject.toml file.

    Returns:
        dict: A dictionary mapping dependency names to their details dictionaries.
    """
    try:
        with open(pyproject_path, "r") as f:
            data = tomlkit.load(f)
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)

    dependencies = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    git_deps = {
        name: details
        for name, details in dependencies.items()
        if isinstance(details, dict) and "git" in details
    }
    return git_deps

def update_dependency_versions(pyproject_path, new_version):
    """
    Update versions for local (path) dependencies in a pyproject.toml file.

    For each dependency that is defined as a table with a "path" key:
      - The dependency’s version is updated to f"^{new_version}" in the parent pyproject.toml.
      - Attempts to update the dependency's own pyproject.toml (if found in the given path)
        by setting its version to new_version.

    Args:
        pyproject_path (str): Path to the parent pyproject.toml file.
        new_version (str): The new version string to set (without the caret).

    Returns:
        None
    """
    try:
        with open(pyproject_path, "r") as f:
            data = tomlkit.load(f)
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)

    poetry_section = data.get("tool", {}).get("poetry", {})
    dependencies = poetry_section.get("dependencies", {})
    updated_deps = {}
    base_dir = os.path.dirname(pyproject_path)

    for dep_name, details in dependencies.items():
        if isinstance(details, dict) and "path" in details:
            # Create a new dependency definition with an updated version.
            new_dep = {"version": f"^{new_version}"}
            # Preserve any additional keys (except we override version).
            for key, value in details.items():
                if key != "path":
                    new_dep[key] = value
            updated_deps[dep_name] = new_dep

            # Attempt to update the dependency's own pyproject.toml (if it exists).
            dependency_path = os.path.join(base_dir, details["path"])
            dependency_pyproject = os.path.join(dependency_path, "pyproject.toml")
            if os.path.isfile(dependency_pyproject):
                try:
                    with open(dependency_pyproject, "r") as dep_file:
                        dep_data = tomlkit.load(dep_file)
                    if "tool" in dep_data and "poetry" in dep_data["tool"]:
                        dep_data["tool"]["poetry"]["version"] = new_version
                        with open(dependency_pyproject, "w") as dep_file:
                            tomlkit.dump(dep_data, dep_file)
                        print(f"Updated {dependency_pyproject} to version {new_version}")
                    else:
                        print(f"Invalid structure in {dependency_pyproject}", file=sys.stderr)
                except Exception as e:
                    print(f"Error updating {dependency_pyproject}: {e}", file=sys.stderr)
        else:
            updated_deps[dep_name] = details

    # Write the updated dependencies back to the parent pyproject.toml.
    data["tool"]["poetry"]["dependencies"] = updated_deps
    try:
        with open(pyproject_path, "w") as f:
            tomlkit.dump(data, f)
        print(f"Updated dependency versions in {pyproject_path}")
    except Exception as e:
        print(f"Error writing updated file {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)


def find_pyproject_files(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    default_filename: str = "pyproject.toml"
) -> List[str]:
    """
    Resolve which pyproject.toml file(s) to operate on.
      1. If `file` is provided, return just that file.
      2. Else if `directory` is provided:
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