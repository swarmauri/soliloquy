#!/usr/bin/env python3
"""
remote_ops.py

Fixes:
  - Preserves original 'optional' status for Git deps instead of forcing optional=True.
  - Does not forcibly create [tool.poetry.extras] if none existed.
  - If a dep was already optional or was in extras, remains optional. Otherwise, stays non-optional.
  - If version cannot be fetched, do not automatically mark it optional unless it was optional before.

"""

import os
from urllib.parse import urljoin

import requests
from tomlkit import parse, dumps, inline_table

# If you have this function in pyproject_ops, import it:
# from .pyproject_ops import find_pyproject_files
# For demonstration, we'll assume it's imported.


def fetch_remote_pyproject_version(git_url, branch="main", subdirectory=""):
    """
    (unchanged)
    """
    try:
        if "github.com" not in git_url:
            raise ValueError("Only GitHub repositories are supported by this function.")
        
        # Remove trailing .git if present.
        repo_path = git_url.split("github.com/")[1]
        if repo_path.endswith(".git"):
            repo_path = repo_path[:-4]
        
        # Build the raw URL; ensure subdirectory ends with "/" if provided.
        base_url = f"https://raw.githubusercontent.com/{repo_path}/{branch}/"
        if subdirectory and not subdirectory.endswith("/"):
            subdirectory += "/"
        pyproject_url = urljoin(base_url, f"{subdirectory}pyproject.toml")
        
        response = requests.get(pyproject_url)
        response.raise_for_status()
        doc = parse(response.text)
        version = doc.get("tool", {}).get("poetry", {}).get("version")
        if version is None:
            print(f"Version key not found in remote pyproject.toml from {pyproject_url}")
        return version
    except Exception as e:
        print(f"Error fetching pyproject.toml from {git_url}: {e}")
        return None


def update_pyproject_with_versions(file_path):
    """
    Reads the local pyproject.toml file and updates Git-based dependencies by:
      - Fetching the remote version (if possible).
      - Preserving the original 'optional' status unless it was previously optional or listed in extras.
      - Only adding an extras section if one already existed or if we need to preserve an existing one.
    """
    # 1) Load the pyproject.toml
    try:
        with open(file_path, "r") as f:
            content = f.read()
        doc = parse(content)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

    # Attempt to retrieve relevant sections
    try:
        tool_section = doc["tool"]
        poetry_section = tool_section["poetry"]
    except KeyError:
        print(f"Error: Invalid pyproject.toml structure in {file_path}.", flush=True)
        return None

    dependencies = poetry_section.get("dependencies", {})
    # We only track 'extras' if it actually exists in the doc:
    #   we'll store a boolean if it was originally present.
    had_extras_section = "extras" in poetry_section
    extras = poetry_section.get("extras", {})

    # Helper function: was the dep in any extras list?
    def dep_is_in_extras(dep_name):
        for _, extra_deps in extras.items():
            if dep_name in extra_deps:
                return True
        return False

    for dep_name, details in dependencies.items():
        # Skip non-dict or dict without 'git' key
        if not (isinstance(details, dict) and "git" in details):
            continue

        # We have a Git-based dependency
        git_url = details["git"]
        branch = details.get("branch", "main")
        subdirectory = details.get("subdirectory", "")
        print(f"\nUpdating Git dependency '{dep_name}':")
        print(f"  Repository: {git_url}")
        print(f"  Branch: {branch}")
        print(f"  Subdirectory: {subdirectory}")

        # Keep track of whether this dependency was optional
        #  either because it was explicitly optional or it was in an extras array
        originally_optional = bool(details.get("optional", False)) or dep_is_in_extras(dep_name)

        remote_version = fetch_remote_pyproject_version(git_url, branch=branch, subdirectory=subdirectory)
        if remote_version:
            print(f"  Fetched version: {remote_version}")
            # Create an inline table
            dep_inline = inline_table()
            dep_inline["version"] = f"^{remote_version}"
            if originally_optional:
                # Only mark optional if it was already optional or in extras
                dep_inline["optional"] = True

            # Preserve any other keys that you want (like 'extras' or 'branch' if you prefer).
            # For example, if you'd like to preserve 'branch':
            # if "branch" in details: dep_inline["branch"] = details["branch"]

            dependencies[dep_name] = dep_inline
        else:
            print(f"  Could not fetch remote version for '{dep_name}'.")
            # If it was originally optional, keep it that way; otherwise do not force optional
            if originally_optional:
                details["optional"] = True
            else:
                details.pop("optional", None)  # Remove optional if set

            dependencies[dep_name] = details

    # Next, we only rewrite the [extras] section if it existed or changed in some relevant way
    # However, you might want to "clean" it so that it only references existing dependencies
    # if it existed in the original doc:
    if had_extras_section:
        # Clean existing extras so that each extra only references valid dependencies
        for extra_name, extra_deps in extras.items():
            extras[extra_name] = [dep for dep in extra_deps if dep in dependencies]
        poetry_section["extras"] = extras  # Reassign
    else:
        # If 'extras' didn't exist originally, do not forcibly create it
        if "extras" in poetry_section:
            del poetry_section["extras"]  # remove if we accidentally created an empty table

    # Update the doc with any changes to dependencies
    poetry_section["dependencies"] = dependencies

    return doc


def update_and_write_pyproject(input_file_path, output_file_path=None):
    """
    Updates the specified pyproject.toml file with resolved versions for Git-based dependencies 
    and writes the updated document to a file.

    Returns True on success, False otherwise.
    """
    updated_doc = update_pyproject_with_versions(input_file_path)
    if updated_doc is None:
        print("Failed to update the pyproject.toml document.")
        return False

    # If no output_file_path is given, overwrite the original
    output_file_path = output_file_path or input_file_path

    try:
        with open(output_file_path, "w") as f:
            f.write(dumps(updated_doc))
        print(f"Updated pyproject.toml written to {output_file_path}")
        return True
    except Exception as e:
        print(f"Error writing updated pyproject.toml: {e}")
        return False


# Example "bulk" function to handle -f/-d/-R logic:
from .pyproject_ops import find_pyproject_files

def remote_update_bulk(file=None, directory=None, recursive=False, output=None) -> None:
    """
    Updates one or more pyproject.toml files by resolving Git-based dependencies
    and fetching remote versions.

    :param file: Explicit path to a pyproject.toml
    :param directory: Path to a directory that has (or contains) pyproject.toml
    :param recursive: If True, search subdirectories for pyproject.toml
    :param output: Optional output file path (applies only if a single file is found)

    We'll:
      - Find the relevant pyproject files
      - For each file, call update_and_write_pyproject()
      - Not forcibly add [tool.poetry.extras] if none existed
      - Only set `optional=true` if it was originally optional or in extras
    """
    try:
        pyproject_files = find_pyproject_files(
            file=file, directory=directory, recursive=recursive
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        print(f"Error discovering pyproject files: {e}")
        return

    # If multiple files are found, but user provided a single output path:
    if output and len(pyproject_files) > 1:
        print("Warning: Multiple pyproject files found but only one --output was provided.\n"
              "We'll update each file in-place. If you intended separate outputs, run individually.\n")

    for i, pyproj_file in enumerate(pyproject_files, start=1):
        # Only use 'output' if there's exactly one file
        out_file = output if (output and len(pyproject_files) == 1) else None

        print(f"\n---\n[{i}/{len(pyproject_files)}] Updating remote deps for: {pyproj_file}")
        success = update_and_write_pyproject(pyproj_file, out_file)
        if not success:
            print(f"Failed to update remote deps in {pyproj_file}.")
            # Decide if you want to break or keep going
