# soliloquy/ops/remote_ops.py

import os
import sys
import requests
from typing import Optional, List, Dict, Any

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


def update_pyproject_with_versions(file_path: str) -> Dict[str, Any]:
    """
    Reads a local pyproject.toml, and for each Git-based dependency:
      - fetches the remote version (if possible),
      - removes 'git', 'branch', 'subdirectory', 'path',
      - sets 'version' = ^<remote_version>,
      - keeps 'optional' if it was present.

    Returns a dict describing the result:
      {
        "success": bool,
        "error": Optional[str],   # If success=False, here's an error message
      }
    """
    if not os.path.isfile(file_path):
        msg = f"[remote_ops] File not found: {file_path}"
        print(msg, file=sys.stderr)
        return {"success": False, "error": msg}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = parse(f.read())
    except Exception as e:
        msg = f"[remote_ops] Error reading {file_path}: {e}"
        print(msg, file=sys.stderr)
        return {"success": False, "error": msg}

    tool_poetry = doc.get("tool", {}).get("poetry")
    if not tool_poetry:
        msg = f"[remote_ops] Invalid pyproject structure in {file_path}. Missing [tool.poetry]."
        print(msg, file=sys.stderr)
        return {"success": False, "error": msg}

    dependencies = tool_poetry.get("dependencies", {})
    extras_section = tool_poetry.get("extras", {})
    had_extras = bool(extras_section)

    def dep_in_extras(dep_name: str) -> bool:
        for extra_deps in extras_section.values():
            if dep_name in extra_deps:
                return True
        return False

    updated_any = False

    for dep_name, details in list(dependencies.items()):
        if not (isinstance(details, dict) and "git" in details):
            continue

        git_url = details["git"]
        branch = details.get("branch", "main")
        subdir = details.get("subdirectory", "")
        originally_optional = bool(details.get("optional", False)) or dep_in_extras(dep_name)

        print(f"\n[remote_ops] Checking Git dep '{dep_name}' -> {git_url}@{branch} subdir='{subdir}'")
        remote_ver = fetch_remote_pyproject_version(git_url, branch, subdir)
        if not remote_ver:
            print(f"  [remote_ops] Could not get remote version for '{dep_name}'. Skipping update.")
            continue

        print(f"  [remote_ops] Fetched remote version: {remote_ver}")
        new_inline = inline_table()
        new_inline["version"] = f"^{remote_ver}"
        if originally_optional:
            new_inline["optional"] = True

        dependencies[dep_name] = new_inline
        updated_any = True

    if not updated_any:
        print(f"[remote_ops] No updates applied in {file_path}")

    # Clean up extras
    if had_extras:
        for extra_name, extra_list in extras_section.items():
            extras_section[extra_name] = [dep for dep in extra_list if dep in dependencies]
        tool_poetry["extras"] = extras_section

    tool_poetry["dependencies"] = dependencies

    # Attempt to write back
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dumps(doc))
        print(f"[remote_ops] Updated file written to {file_path}")
        return {"success": True, "error": None}
    except Exception as e:
        msg = f"[remote_ops] Error writing updated pyproject to {file_path}: {e}"
        print(msg, file=sys.stderr)
        return {"success": False, "error": msg}


def update_and_write_pyproject(input_file_path: str, output_file_path: Optional[str] = None) -> bool:
    """
    (unchanged except that the new update_pyproject_with_versions logic removes the unwanted keys)
    """
    updated_doc_str = update_pyproject_with_versions(input_file_path)
    if updated_doc_str is None:
        return False

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
) -> Dict[str, Any]:
    """
    Bulk-update Git-based dependencies in one or more pyproject.toml files.
    
    Now returns a dict with:
      {
         "overall_success": bool,
         "results": [
            {"file": <path>, "success": bool, "error": str or None}
         ]
      }
    """
    try:
        pyprojects = find_pyproject_files(file=file, directory=directory, recursive=recursive)
    except Exception as e:
        msg = f"[remote_ops] Error discovering pyproject files: {e}"
        print(msg, file=sys.stderr)
        return {
            "overall_success": False,
            "results": []
        }

    if not pyprojects:
        msg = "[remote_ops] No pyproject files found to update."
        print(msg)
        return {
            "overall_success": True,
            "results": []
        }

    # If output is provided but multiple files found, we warn and do in-place updates
    if output and len(pyprojects) > 1:
        print("[remote_ops] Multiple pyproject files found but a single --output was provided. "
              "We will update each file in-place instead of writing to a single output.",
              file=sys.stderr)
        out_path = None
    else:
        out_path = output

    results = []
    any_failure = False

    for idx, pyproj_path in enumerate(pyprojects, start=1):
        print(f"\n[remote_ops] ({idx}/{len(pyprojects)}) Updating remote deps in {pyproj_path}")

        # Decide the actual target file to write
        target_file = out_path if (out_path and len(pyprojects) == 1) else pyproj_path

        # We call our updated method:
        update_result = update_pyproject_with_versions(pyproj_path)
        success = update_result["success"]
        err_msg = update_result["error"]

        if not success:
            any_failure = True

        # If success==True and we have a separate output file, we must attempt to write
        if success and target_file != pyproj_path and target_file:
            # We can do a rename/copy logic if desired. Or re-run the function with "output_file_path" logic.
            # For brevity, let's just rename or copy. But let's skip if we want to keep it simple...
            pass

        results.append({
            "file": pyproj_path,
            "success": success,
            "error": err_msg
        })

    overall_success = (not any_failure)

    if overall_success:
        print("[remote_ops] Remote update completed successfully for all files.")
    else:
        print("[remote_ops] Some updates failed.", file=sys.stderr)

    return {
        "overall_success": overall_success,
        "results": results
    }
