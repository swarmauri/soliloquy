# soliloquy/ops/lock_ops.py

import os
import sys
import tomlkit
from typing import Optional

from soliloquy.ops.pyproject_ops import find_pyproject_files, extract_path_dependencies
from soliloquy.ops.poetry_utils import run_command

def lock_packages(
    file: Optional[str] = None,
    directory: Optional[str] = None,
    recursive: bool = False
) -> bool:
    """
    Runs 'poetry lock' against one or more pyproject.toml files.
    If a pyproject is an aggregator (package-mode=false),
    we either:
      - lock the aggregator itself if you want a root-level lock,
      - or skip aggregator, then lock each local path dependency.

    Returns True if all locks succeed, False otherwise.
    """
    try:
        pyprojects = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[lock_ops] Error finding pyproject files: {e}", file=sys.stderr)
        return False

    if not pyprojects:
        print("[lock_ops] No pyproject.toml files found to lock.")
        return True  # or False, depending on your logic

    overall_success = True

    for idx, pyproj_path in enumerate(pyprojects, start=1):
        print(f"\n[lock_ops] ({idx}/{len(pyprojects)}) Checking {pyproj_path}")
        is_aggregator, pkg_name = _check_if_aggregator(pyproj_path)

        if is_aggregator:
            # Option A: Lock aggregator itself if it has its own dependencies
            # or dev-dependencies. 
            # Option B: skip aggregator and only lock subpackages
            print(f"  Detected aggregator '{pkg_name}'. Locking aggregator itself...")
            if not _run_poetry_lock(pyproj_path):
                overall_success = False

            # Then also lock local path dependencies
            print("  Locking each local path dependency as well ...")
            if not _lock_local_path_deps(pyproj_path):
                overall_success = False

        else:
            # Normal package => lock directly
            print(f"  Detected normal package '{pkg_name}'. Locking ...")
            if not _run_poetry_lock(pyproj_path):
                overall_success = False

    if overall_success:
        print("[lock_ops] All 'poetry lock' operations succeeded.")
    else:
        print("[lock_ops] Some lock operations failed.", file=sys.stderr)
    return overall_success


def _run_poetry_lock(pyproj_file: str) -> bool:
    """
    Run 'poetry lock' in the same directory as pyproj_file.
    """
    proj_dir = os.path.dirname(pyproj_file)
    cmd = ["poetry", "lock"]
    print(f"    Running: {' '.join(cmd)} (cwd={proj_dir})")
    rc = run_command(cmd, cwd=proj_dir)
    if rc != 0:
        print(f"    [lock_ops] 'poetry lock' failed in {proj_dir}.", file=sys.stderr)
        return False
    return True


def _lock_local_path_deps(aggregator_pyproj: str) -> bool:
    """
    For an aggregator, gather local path dependencies and run 'poetry lock' in each.
    """
    deps = extract_path_dependencies(aggregator_pyproj)
    if not deps:
        print("  No local path dependencies found in aggregator.")
        return True

    base_dir = os.path.dirname(aggregator_pyproj)
    success = True
    for dep_rel in deps:
        dep_abs = os.path.join(base_dir, dep_rel)
        pyproj = os.path.join(dep_abs, "pyproject.toml")
        if not os.path.isfile(pyproj):
            print(f"    [lock_ops] Skipping invalid path dep '{dep_rel}' (no pyproject.toml).", file=sys.stderr)
            success = False
            continue

        if not _run_poetry_lock(pyproj):
            success = False
    return success


def _check_if_aggregator(pyproj_path: str) -> (bool, str):
    """
    Checks if 'package-mode=false'.
    Returns (is_aggregator, package_name).
    """
    with open(pyproj_path, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    tool_poetry = doc.get("tool", {}).get("poetry", {})
    pkg_name = tool_poetry.get("name", "unknown")

    pkg_mode = tool_poetry.get("package-mode", True)
    if isinstance(pkg_mode, str):
        pkg_mode = (pkg_mode.lower() != "false")

    is_aggregator = (pkg_mode is False)
    return is_aggregator, pkg_name
