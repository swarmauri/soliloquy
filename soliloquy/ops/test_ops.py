# soliloquy/ops/test_ops.py

import os
import sys
import subprocess
from typing import Dict, List, Union

import tomlkit

from soliloquy.ops.pyproject_ops import (
    find_pyproject_files,
    extract_path_dependencies
)
from soliloquy.ops.poetry_utils import run_command  # For uniform command calls, if desired


def run_pytests(test_directory: str = ".", num_workers: int = 1) -> Dict[str, Union[bool, int, str]]:
    """
    Runs pytest (via 'poetry run pytest') in the given directory.
    If num_workers > 1, runs pytest with '-n <num_workers>' for parallel tests.

    Returns a dict with:
      {
        "success": bool,        # True if returncode == 0
        "returncode": int,      # The actual exit code from pytest
        "directory": str,       # The directory tested
      }
    """
    cmd = ["poetry", "run", "pytest"]
    if num_workers > 1:
        cmd.extend(["-n", str(num_workers)])
    print(f"[test_ops] Running tests in {test_directory} -> {' '.join(cmd)}")

    # You can choose between using run_command(...) or direct subprocess.run(...)
    # Example below uses direct subprocess.run:
    proc = subprocess.run(cmd, cwd=test_directory)
    rc = proc.returncode

    return {
        "success": (rc == 0),
        "returncode": rc,
        "directory": test_directory,
    }


def run_tests_with_mode(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    mode: str = "single",
    num_workers: int = 1
) -> Dict[str, Union[bool, List[Dict[str, Union[bool, int, str]]]]]:
    """
    Entry point to run tests according to a 'mode'.

    Args:
        file: Path to a single pyproject.toml (standalone).
        directory: Directory with packages or aggregator.
        recursive: If True, find multiple pyprojects recursively (used for fallback).
        mode: "single", "monorepo", or "each".
        num_workers: Parallel workers for pytest (-n).

    Returns:
      {
        "success": bool,            # True if all tests pass
        "details": List[dict],      # A list of test result dicts from run_pytests
      }
    """
    if mode not in ("single", "monorepo", "each"):
        print(f"[test_ops] Invalid test mode: {mode}", file=sys.stderr)
        return {"success": False, "details": []}

    # We might need to identify the relevant pyproject to see if aggregator or not
    try:
        pyprojects = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[test_ops] Error finding pyproject files: {e}", file=sys.stderr)
        return {"success": False, "details": []}

    # If no pyproject found, fallback to simple single test in directory
    if not pyprojects:
        print("[test_ops] No pyproject.toml found. Running single test in the specified directory.")
        test_dir = directory or "."
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result]}

    # For simplicity, we only consider the first pyproject if multiple are found,
    # unless we are in "each" mode. This is arbitrary; adapt to your scenario.
    primary_pyproj = pyprojects[0]
    aggregator, pkg_name = _check_if_aggregator(primary_pyproj)

    if mode == "single":
        # Just run 1 test in the directory (like a standalone approach)
        test_dir = directory or os.path.dirname(primary_pyproj)
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result]}

    elif mode == "monorepo":
        # Run a single test from the top-level directory (like one big combined run)
        test_dir = directory or os.path.dirname(primary_pyproj)
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result]}

    else:  # mode == "each"
        # If aggregator => gather path deps, test each
        # else => fallback to finding multiple pyprojects, test each individually
        all_passed = True
        details = []

        if aggregator:
            print(f"[test_ops] Aggregator detected ('package-mode=false'), testing each path dependency individually.")
            deps = extract_path_dependencies(primary_pyproj)
            base_dir = os.path.dirname(primary_pyproj)

            for dep_rel_path in deps:
                subpkg_path = os.path.join(base_dir, dep_rel_path)
                if not os.path.isdir(subpkg_path):
                    print(f"  Skipping invalid subpackage dir: {subpkg_path}", file=sys.stderr)
                    all_passed = False
                    continue
                r = run_pytests(subpkg_path, num_workers)
                details.append(r)
                if not r["success"]:
                    all_passed = False
        else:
            print("[test_ops] No aggregator found. We'll test each discovered pyproject in subdirs individually.")
            for pyproj in pyprojects:
                proj_dir = os.path.dirname(pyproj)
                # If the project dir is the same as root (and we have multiple pyprojects),
                # you might skip it if you think it's the aggregator. 
                # We'll skip only if aggregator is indeed found. But aggregator is false, so let's just run it:
                r = run_pytests(proj_dir, num_workers)
                details.append(r)
                if not r["success"]:
                    all_passed = False

        return {"success": all_passed, "details": details}


def _check_if_aggregator(pyproj_path: str) -> (bool, str):
    """
    Parses 'pyproj_path' with tomlkit and checks if [tool.poetry.package-mode] is False.
    Returns:
      (is_aggregator, package_name)
    """
    with open(pyproj_path, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    poetry_table = doc.get("tool", {}).get("poetry", {})
    pkg_name = poetry_table.get("name", "unknown")

    pkg_mode = poetry_table.get("package-mode", True)
    if isinstance(pkg_mode, str):
        # if "false" as string => aggregator
        pkg_mode = (pkg_mode.lower() != "false")

    is_aggregator = (pkg_mode is False)
    return is_aggregator, pkg_name
