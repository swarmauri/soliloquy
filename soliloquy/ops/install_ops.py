# soliloquy/ops/install_ops.py

import os
import sys
import tomlkit
from typing import Optional

from soliloquy.ops.pyproject_ops import find_pyproject_files, extract_path_dependencies
from soliloquy.ops.poetry_utils import run_command

def install_packages(
    file: Optional[str] = None,
    directory: Optional[str] = None,
    recursive: bool = False
) -> bool:
    """
    Finds pyproject.toml files (via file/directory/recursive),
    determines if each is a normal package or an aggregator,
    and then runs 'poetry install' accordingly:
      - For normal packages (package-mode=true or missing the key):
          We install the package itself (poetry install in that dir).
      - For an aggregator (package-mode=false):
          We skip installing the aggregator itself, but install each
          local path dependency.

    Returns:
      True if all installs succeed, False otherwise.
    """
    try:
        pyprojects = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[install_ops] Error discovering pyproject files: {e}", file=sys.stderr)
        return False

    if not pyprojects:
        print("[install_ops] No pyproject.toml files found to install.")
        return True  # or False, depending on your workflow

    overall_success = True

    for idx, pyproj_path in enumerate(pyprojects, start=1):
        print(f"\n[install_ops] ({idx}/{len(pyprojects)}) Examining: {pyproj_path}")
        is_aggregator, pkg_name = _check_if_aggregator(pyproj_path)

        if is_aggregator:
            print(f"  Detected aggregator '{pkg_name}' (package-mode=false). Skipping aggregator install.")
            # Instead, install each local path dependency
            proj_dir = os.path.dirname(pyproj_path)  # Use the directory instead of the file path
            success = _run_poetry_install(proj_dir, extras=True)
            if not success:
                overall_success = False

        else:
            # Normal package => install it
            print(f"  Detected normal package '{pkg_name}'. Installing ...")
            proj_dir = os.path.dirname(pyproj_path)
            success = _run_poetry_install(proj_dir)
            if not success:
                overall_success = False

    if overall_success:
        print("[install_ops] All installs completed successfully.")
    else:
        print("[install_ops] Some installs failed.", file=sys.stderr)
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
        # If it's "false" as a string, treat it as aggregator
        pkg_mode = (pkg_mode.lower() != "false")

    is_aggregator = (pkg_mode is False)
    return is_aggregator, pkg_name

def _run_poetry_install(package_dir: str, extras: bool = True) -> bool:
    """
    Helper that runs 'poetry install' in the given directory.
    Returns True if successful, False otherwise.
    """
    cmd = ["poetry", "install", "--no-cache", "-vv"]
    if extras:
        cmd.append("--all-extras")
    print(f"      Running: {' '.join(cmd)} (cwd={package_dir})")

    rc = run_command(cmd, cwd=package_dir)
    if rc != 0:
        print(f"      Install failed in {package_dir} (exit code {rc}).", file=sys.stderr)
        return False
    return True
