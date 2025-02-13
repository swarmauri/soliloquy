# soliloquy/ops/build_ops.py

import os
import sys
from typing import Optional, List

import tomlkit
from soliloquy.ops.pyproject_ops import find_pyproject_files, extract_path_dependencies
from soliloquy.ops.poetry_utils import run_command  # Updated run_command returns (rc, stdout, stderr)

def build_packages(
    file: Optional[str] = None,
    directory: Optional[str] = None,
    recursive: bool = False
) -> bool:
    """
    Finds pyproject.toml files (via file/directory/recursive),
    determines if each is a normal package or an aggregator,
    and then runs 'poetry build' where applicable:
      - For normal packages (package-mode=true or missing),
        we build the package itself.
      - For an aggregator (package-mode=false),
        we skip building it directly, but we build each local
        path dependency referenced in it.

    Returns:
        True if all builds succeed, False otherwise.
    """
    try:
        pyprojects = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[build_ops] Error finding pyproject files: {e}", file=sys.stderr)
        return False

    overall_success = True

    for pyproj_path in pyprojects:
        print(f"\n[build_ops] Examining: {pyproj_path}")
        is_aggregator, pkg_name = _check_if_aggregator(pyproj_path)

        if is_aggregator:
            print(f"  Detected aggregator (package-mode=false). Skipping build of aggregator itself.")
            # Instead, build local path dependencies
            success = _build_local_path_dependencies(pyproj_path)
            if not success:
                overall_success = False
        else:
            # Normal package => build it
            print(f"  Detected normal package '{pkg_name}'. Building ...")
            proj_dir = os.path.dirname(pyproj_path)
            success = _run_poetry_build(proj_dir)
            if not success:
                overall_success = False

    if overall_success:
        print("\n[build_ops] All builds completed successfully.")
    else:
        print("\n[build_ops] Some builds failed.", file=sys.stderr)
    return overall_success


def _check_if_aggregator(pyproj_path: str) -> (bool, str):
    """
    Parses the given pyproject.toml with tomlkit, returns:
      (is_aggregator: bool, package_name: str or 'unknown')

    - aggregator if tool.poetry.package-mode == false
    - normal package otherwise
    - if name is missing, returns 'unknown'
    """
    with open(pyproj_path, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    tool_poetry = doc.get("tool", {}).get("poetry", {})
    pkg_name = tool_poetry.get("name", "unknown")

    # If package-mode is explicitly false, treat as aggregator
    pkg_mode = tool_poetry.get("package-mode", True)
    # Convert to bool if it's a string
    if isinstance(pkg_mode, str):
        pkg_mode = (pkg_mode.lower() != "false")

    is_aggregator = (pkg_mode is False)
    return is_aggregator, pkg_name


def _build_local_path_dependencies(pyproj_path: str) -> bool:
    """
    For the aggregator pyproject, gather local path dependencies
    and build each. Returns True if all succeed, otherwise False.
    """
    deps = extract_path_dependencies(pyproj_path)
    if not deps:
        print("  No local path dependencies found to build.")
        return True

    base_dir = os.path.dirname(pyproj_path)
    overall_success = True

    print(f"  Found {len(deps)} local path dependencies. Building each ...")
    for dep_rel_path in deps:
        dep_abs_path = os.path.join(base_dir, dep_rel_path)
        dep_pyproj = os.path.join(dep_abs_path, "pyproject.toml")

        if not os.path.isdir(dep_abs_path) or not os.path.isfile(dep_pyproj):
            print(f"    Skipping invalid path dependency {dep_rel_path} (no pyproject.toml).", file=sys.stderr)
            overall_success = False
            continue

        print(f"    Building local path dependency at {dep_abs_path} ...")
        success = _run_poetry_build(dep_abs_path)
        if not success:
            overall_success = False
    return overall_success


def _run_poetry_build(package_dir: str) -> bool:
    """
    Helper that runs 'poetry build' in the given directory.
    Returns True if successful, False otherwise.
    """
    cmd = ["poetry", "build"]
    print(f"      Running: {' '.join(cmd)} (cwd={package_dir})")

    rc, out, err = run_command(cmd, cwd=package_dir)
    if rc != 0:
        print(f"      Build failed in {package_dir} (exit code {rc}).", file=sys.stderr)
        if out:
            print(f"      STDOUT: {out}")
        if err:
            print(f"      STDERR: {err}", file=sys.stderr)
        return False
    return True
