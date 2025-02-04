# soliloquy/ops/publish_ops.py

import os
import sys
import tomlkit
from typing import Optional

from soliloquy.ops.pyproject_ops import find_pyproject_files, extract_path_dependencies
from soliloquy.ops.poetry_utils import run_command  # or use subprocess directly


def publish_packages(
    file: Optional[str] = None,
    directory: Optional[str] = None,
    recursive: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
    repository: Optional[str] = None
) -> bool:
    """
    Discovers pyproject.toml files using (file | directory + recursive).
    For each discovered file:
      - If aggregator (package-mode=false): skip publishing that aggregator,
        but publish each local path dependency found in it.
      - Else, build + publish the package from that directory.

    username/password: If provided, pass them to 'poetry publish' as --username, --password.
                      If None, relies on Poetry config or interactive prompts.
    repository: If provided, pass '--repository <name>' to poetry publish for a custom index.

    Returns:
      True if all publishes succeeded, False otherwise.
    """
    try:
        pyproject_files = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[publish_ops] Error discovering pyproject files: {e}", file=sys.stderr)
        return False

    if not pyproject_files:
        print("[publish_ops] No pyproject.toml files found for publishing.")
        return True  # or False, depending on your desired logic

    overall_success = True
    for idx, pyproj_path in enumerate(pyproject_files, start=1):
        print(f"\n[publish_ops] ({idx}/{len(pyproject_files)}) Examining {pyproj_path}")
        is_aggregator, pkg_name = _check_if_aggregator(pyproj_path)

        if is_aggregator:
            print(f"  '{pkg_name}' is an aggregator. We won't publish aggregator itself. Publishing path deps ...")
            success = _publish_local_path_deps(pyproj_path, username, password, repository)
            if not success:
                overall_success = False
        else:
            # Normal package => build & publish
            success = _build_and_publish(pyproj_path, username, password, repository)
            if not success:
                overall_success = False

    if overall_success:
        print("[publish_ops] All publishes completed successfully.")
    else:
        print("[publish_ops] Some publishes failed.", file=sys.stderr)
    return overall_success


def _check_if_aggregator(pyproj_path: str) -> (bool, str):
    """
    Reads pyproj_path with tomlkit, checks if [tool.poetry].package-mode == false.
    Returns:
      (is_aggregator: bool, package_name: str)
    """
    with open(pyproj_path, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())

    tool_poetry = doc.get("tool", {}).get("poetry", {})
    pkg_name = tool_poetry.get("name", "unknown")

    pkg_mode = tool_poetry.get("package-mode", True)
    if isinstance(pkg_mode, str):
        # If it's the string "false", interpret as aggregator
        pkg_mode = (pkg_mode.lower() != "false")

    is_aggregator = (pkg_mode is False)
    return is_aggregator, pkg_name


def _publish_local_path_deps(
    aggregator_pyproj: str,
    username: Optional[str],
    password: Optional[str],
    repository: Optional[str]
) -> bool:
    """
    Extracts local path dependencies from the aggregator's pyproject,
    calls _build_and_publish(...) on each. Returns True if all succeed.
    """
    base_dir = os.path.dirname(aggregator_pyproj)
    deps = extract_path_dependencies(aggregator_pyproj)
    if not deps:
        print("  No local path dependencies found in aggregator.")
        return True

    all_ok = True
    for dep_rel in deps:
        dep_abs = os.path.join(base_dir, dep_rel)
        pyproj = os.path.join(dep_abs, "pyproject.toml")
        if not os.path.isfile(pyproj):
            print(f"  [publish_ops] Skipping invalid path dep '{dep_rel}' (no pyproject.toml).", file=sys.stderr)
            all_ok = False
            continue

        success = _build_and_publish(pyproj, username, password, repository)
        if not success:
            all_ok = False

    return all_ok


def _build_and_publish(
    pyproj_file: str,
    username: Optional[str],
    password: Optional[str],
    repository: Optional[str]
) -> bool:
    """
    Builds and publishes a single package described by 'pyproj_file'.
    Returns True if successful, False otherwise.
    """
    package_dir = os.path.dirname(pyproj_file)
    print(f"  Building package in {package_dir} ...")
    rc_build = run_command(["poetry", "build"], cwd=package_dir)
    if rc_build != 0:
        print(f"  [publish_ops] Build failed in {package_dir}.", file=sys.stderr)
        return False

    print(f"  Publishing package from {package_dir} ...")
    cmd = ["poetry", "publish"]
    # If we want verbose output, we might do cmd.append("-vv").

    if username:
        cmd.extend(["--username", username])
    if password:
        cmd.extend(["--password", password])
    if repository:
        cmd.extend(["--repository", repository])

    rc_publish = run_command(cmd, cwd=package_dir)
    if rc_publish != 0:
        print(f"  [publish_ops] Publish failed in {package_dir} (exit={rc_publish}).", file=sys.stderr)
        return False

    return True
