# soliloquy/ops/remote_ops.py

import os
import sys
import requests
from typing import Optional, List

from urllib.parse import urljoin
from tomlkit import parse, dumps, inline_table

# If you have a function for discovering relevant pyproject.toml files:
from soliloquy.ops.pyproject_ops import find_pyproject_files

def fetch_remote_pyproject_version(
    git_url: str,
    branch: str = "main",
    subdirectory: str = ""
) -> Optional[str]:
    """
    Attempts to fetch a remote pyproject.toml (on GitHub) and parse out
    the [tool.poetry].version field.

    - Only handles GitHub repos at the moment.
    - If subdirectory is provided, it is appended to the raw URL path.

    Returns:
        The version string (e.g. '1.2.3') if found, else None.
    """
    if "github.com" not in git_url:
        print(f"[remote_ops] Currently only supports GitHub: {git_url}", file=sys.stderr)
        return None

    # Remove trailing .git if present
    repo_path = git_url.split("github.com/")[-1]
    if repo_path.endswith(".git"):
        repo_path = repo_path[:-4]

    # Construct the raw URL to the pyproject.toml
    # e.g. https://raw.githubusercontent.com/<user>/<repo>/<branch>/<subdirectory>/pyproject.toml
    base_url = f"https://raw.githubusercontent.com/{repo_path}/{branch}/"
    if subdirectory and not subdirectory.endswith("/"):
        subdirectory += "/"
    pyproject_url = urljoin(base_url, f"{subdirectory}pyproject.toml")

    print(f"[remote_ops] Fetching remote pyproject from {pyproject_url}")
    try:
        resp = requests.get(pyproject_url)
        resp.raise_for_status()
    except Exception as e:
        print(f"[remote_ops] Failed to fetch {pyproject_url}: {e}", file=sys.stderr)
        return None

    try:
        doc = parse(resp.text)
        version = doc.get("tool", {}).get("poetry", {}).get("version")
        if not version:
            print(f"[remote_ops] No version found in remote pyproject.toml at {pyproject_url}", file=sys.stderr)
            return None
        return version
    except Exception as e:
        print(f"[remote_ops] Could not parse remote TOML: {e}", file=sys.stderr)
        return None


def update_pyproject_with_versions(file_path: str) -> Optional[str]:
    """
    Reads a local pyproject.toml, and for each Git-based dependency:
      - fetches the remote version (if possible),
      - updates that dependency's version to ^<remote_version>,
      - preserves original 'optional' status or extras membership.

    Returns:
      The updated TOML string (if changes made or not),
      or None if an error occurred (like invalid structure).
    """
    if not os.path.isfile(file_path):
        print(f"[remote_ops] File not found: {file_path}", file=sys.stderr)
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = parse(f.read())
    except Exception as e:
        print(f"[remote_ops] Error reading {file_path}: {e}", file=sys.stderr)
        return None

    # Locate [tool.poetry] section
    tool_poetry = doc.get("tool", {}).get("poetry")
    if not tool_poetry:
        print(f"[remote_ops] Invalid pyproject structure in {file_path}. Missing [tool.poetry].", file=sys.stderr)
        return None

    dependencies = tool_poetry.get("dependencies", {})
    # If [tool.poetry.extras] section exists, store it for references
    extras_section = tool_poetry.get("extras", {})
    had_extras = bool(extras_section)

    def dep_in_extras(dep_name: str) -> bool:
        # Checks if dep_name is listed in any extras array
        for extra_deps in extras_section.values():
            if dep_name in extra_deps:
                return True
        return False

    # For each dependency, if it has "git", we attempt to fetch version
    updated_any = False

    for dep_name, details in list(dependencies.items()):
        if not (isinstance(details, dict) and "git" in details):
            # not a git-based dependency
            continue

        git_url = details["git"]
        branch = details.get("branch", "main")
        subdir = details.get("subdirectory", "")
        print(f"\n[remote_ops] Checking Git dep '{dep_name}' -> {git_url}@{branch} subdir='{subdir}'")

        # Keep track of if it was originally optional
        originally_optional = bool(details.get("optional", False)) or dep_in_extras(dep_name)

        remote_ver = fetch_remote_pyproject_version(git_url, branch, subdir)
        if not remote_ver:
            # If we fail to fetch a remote version, we won't force a change. 
            # You could optionally mark them optional if you want, or skip entirely.
            print(f"  [remote_ops] Could not get remote version for '{dep_name}'. Skipping update.")
            continue

        print(f"  [remote_ops] Fetched remote version: {remote_ver}")

        # Build a new inline table with ^version
        new_inline = inline_table()
        new_inline["version"] = f"^{remote_ver}"

        # Preserve optional if it was originally optional
        if originally_optional:
            new_inline["optional"] = True

        # We also preserve other keys like 'git', 'branch', 'subdirectory' if you want:
        new_inline["git"] = git_url
        if "branch" in details:
            new_inline["branch"] = details["branch"]
        if "subdirectory" in details:
            new_inline["subdirectory"] = details["subdirectory"]

        # Update the dictionary
        dependencies[dep_name] = new_inline
        updated_any = True

    # If no changes, just return the original content as TOML string
    if not updated_any:
        print(f"[remote_ops] No updates applied in {file_path}")
        return dumps(doc)

    # Optionally clean extras so that each extra only references existing dependencies
    if had_extras:
        for extra_name, extra_list in extras_section.items():
            # remove anything that doesn't exist in dependencies now
            extras_section[extra_name] = [dep for dep in extra_list if dep in dependencies]
        tool_poetry["extras"] = extras_section  # reassign

    tool_poetry["dependencies"] = dependencies
    return dumps(doc)


def update_and_write_pyproject(input_file_path: str, output_file_path: Optional[str] = None) -> bool:
    """
    Reads a pyproject.toml from input_file_path, updates Git deps with remote versions,
    writes the result back to 'output_file_path' or overwrites the original.

    Returns True on success (even if no changes), False on error.
    """
    updated_doc_str = update_pyproject_with_versions(input_file_path)
    if updated_doc_str is None:
        return False

    # If no output path, overwrite the original
    target = output_file_path or input_file_path
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(updated_doc_str)
        print(f"[remote_ops] Updated file written to {target}")
        return True
    except Exception as e:
        print(f"[remote_ops] Error writing updated pyproject to {target}: {e}", file=sys.stderr)
        return False


def remote_update_bulk(
    file: Optional[str] = None,
    directory: Optional[str] = None,
    recursive: bool = False,
    output: Optional[str] = None
) -> bool:
    """
    Bulk-update Git-based dependencies in one or more pyproject.toml files.
    
    - If 'file' is provided, updates that one file.
    - Else if 'directory' is provided:
        * If 'recursive=True', find all pyproject.toml in subdirectories.
        * Otherwise, just that single 'directory/pyproject.toml' (if present).
    - 'output': If exactly one pyproject file is found, you can direct the updated
      content to a new path. If multiple are found but 'output' is set, 
      we log a warning and just update each in-place.

    Returns:
      True if all updates are successful, False if any file fails to update.
    """
    try:
        pyprojects = find_pyproject_files(file=file, directory=directory, recursive=recursive)
    except Exception as e:
        print(f"[remote_ops] Error discovering pyproject files: {e}", file=sys.stderr)
        return False

    if not pyprojects:
        print("[remote_ops] No pyproject files found to update.")
        return True  # or False, depending on what you consider "success"

    if output and len(pyprojects) > 1:
        print("[remote_ops] Multiple pyproject files found but a single --output was provided. "
              "We will update each file in-place instead of writing to a single output.",
              file=sys.stderr)
        out_path = None
    else:
        out_path = output

    overall_success = True

    for idx, pyproj_path in enumerate(pyprojects, start=1):
        print(f"\n[remote_ops] ({idx}/{len(pyprojects)}) Updating remote deps in {pyproj_path}")
        success = update_and_write_pyproject(
            input_file_path=pyproj_path,
            output_file_path=out_path if len(pyprojects) == 1 else None
        )
        if not success:
            overall_success = False

    if overall_success:
        print("[remote_ops] Remote update completed successfully for all files.")
    else:
        print("[remote_ops] Some updates failed.", file=sys.stderr)

    return overall_success
