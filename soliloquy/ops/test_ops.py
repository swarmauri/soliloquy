# soliloquy/ops/test_ops.py

import os
import sys
import subprocess
import tempfile
import shutil
from typing import Dict, List, Union, Tuple, Optional

import tomlkit

from soliloquy.ops.pyproject_ops import (
    find_pyproject_files,
    extract_path_dependencies,
    extract_git_dependencies
)
from soliloquy.ops.poetry_utils import run_command  # For uniform command calls, if desired


def run_pytests(
    test_directory: str = ".",
    num_workers: int = 1
) -> Dict[str, Union[bool, int, str]]:
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
        cmd.extend([
            "-n", 
            str(num_workers), 
            "--dist=loadfile",
            "--dist=loadfile", 
            "--tb=short", 
            "--json-report", 
            "--json-report-file=pytest_results.json"
            ])
    print(f"[test_ops] Running tests in {test_directory} -> {' '.join(cmd)}")

    # Here we directly call subprocess, but you could also use run_command(...) if desired.
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
    num_workers: int = 1,
    cleanup: bool = True
) -> Dict[str, Union[bool, List[Dict[str, Union[bool, int, str]]], Optional[str]]]:
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
        "git_temp_dir": Optional[str],  # Path to the temporary directory with cloned git deps, if any
      }
    """
    if mode not in ("single", "monorepo", "each"):
        print(f"[test_ops] Invalid test mode: {mode}", file=sys.stderr)
        return {"success": False, "details": [], "git_temp_dir": None}

    # ------------------------------------------------------
    # Discover pyprojects
    # ------------------------------------------------------
    try:
        pyprojects = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"[test_ops] Error finding pyproject files: {e}", file=sys.stderr)
        return {"success": False, "details": [], "git_temp_dir": None}

    # If no pyproject found, fallback to single test in the directory
    if not pyprojects:
        print("[test_ops] No pyproject.toml found. Running single test in the specified directory.")
        test_dir = directory or "."
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result], "git_temp_dir": None}

    # We'll consider the first pyproject as "primary" unless mode=each.
    primary_pyproj = pyprojects[0]
    aggregator, pkg_name = _check_if_aggregator(primary_pyproj)

    # ------------------------------------------------------
    # Mode: single
    # ------------------------------------------------------
    if mode == "single":
        # Just run 1 test in the directory (like a standalone approach)
        test_dir = directory or os.path.dirname(primary_pyproj)
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result], "git_temp_dir": None}

    # ------------------------------------------------------
    # Mode: monorepo
    # ------------------------------------------------------
    elif mode == "monorepo":
        # Run a single test from the top-level directory (like one big combined run)
        test_dir = directory or os.path.dirname(primary_pyproj)
        result = run_pytests(test_dir, num_workers)
        return {"success": result["success"], "details": [result], "git_temp_dir": None}

    # ------------------------------------------------------
    # Mode: each
    # ------------------------------------------------------
    else:
        # aggregator => gather path deps & git deps, test each
        # else => fallback to scanning multiple pyprojects
        all_passed = True
        details: List[Dict[str, Union[bool, int, str]]] = []
        git_temp_dir: Optional[str] = None  # To store the temp directory path if any

        if aggregator:
            print(f"[test_ops] Aggregator detected ('package-mode=false'), testing each path dependency individually.")

            # 1) Test local path dependencies
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

            # NEW: 2) Test Git-based dependencies
            git_deps = extract_git_dependencies(primary_pyproj)
            if git_deps:
                # We'll clone them into a single temp folder,
                # run tests in each subdirectory that has a pyproject.toml.
                git_ok, git_tmp_dir = _test_git_deps(git_deps, details, num_workers, cleanup)
                if not git_ok:
                    all_passed = False
                    
                if git_tmp_dir is not None:
                    git_temp_dir = git_tmp_dir


        else:
            # Non-aggregator => we test each discovered pyproject in subdirs individually
            print("[test_ops] No aggregator found. We'll test each discovered pyproject in subdirs individually.")
            # 1) Test local path dependencies
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

            # NEW: 2) Test Git-based dependencies
            git_deps = extract_git_dependencies(primary_pyproj)
            if git_deps:
                # We'll clone them into a single temp folder,
                # run tests in each subdirectory that has a pyproject.toml.
                git_ok, git_tmp_dir = _test_git_deps(git_deps, details, num_workers, cleanup)
                if not git_ok:
                    all_passed = False
                    
                if git_tmp_dir is not None:
                    git_temp_dir = git_tmp_dir

        return {"success": all_passed, "details": details, "git_temp_dir": git_temp_dir}


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


# --------------------------------------------------------------------------
# NEW: Test Git-based dependencies (similar to building them in build_monorepo)
# --------------------------------------------------------------------------
def _test_git_deps(
    git_deps: dict,
    details: List[Dict[str, Union[bool, int, str]]],
    num_workers: int,
    cleanup: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Clones each Git-based dependency, then runs tests on each subdirectory.
    Returns:
      (all_passed, temp_dir)
        - all_passed: bool (True if all tests pass)
        - temp_dir: The path to the temporary clone folder, or None if it was cleaned up.
    """
    import tempfile
    import shutil
    from collections import defaultdict

    # Group by (git_url, branch)
    grouped = defaultdict(list)
    for dep_name, config in git_deps.items():
        git_url = config.get("git")
        branch = config.get("branch", "main")
        subdir = config.get("subdirectory", ".")
        grouped[(git_url, branch)].append((dep_name, subdir))

    if not grouped:
        return True, None

    print(f"[test_ops] Found {len(git_deps)} Git dependencies to test. Cloning & testing each subdir ...")

    all_passed = True
    build_root = tempfile.mkdtemp(prefix="mono_test_")
    print(f"[test_ops] Using temporary directory for Git-based tests: {build_root}")

    try:
        for (git_url, branch), sub_pkgs in grouped.items():
            print(f"\n[test_ops] Cloning {git_url} (branch: {branch}) to test {len(sub_pkgs)} subdir(s).")
            clone_dir_name = branch.replace("/", "-") + "_clone"
            clone_dir = os.path.join(build_root, clone_dir_name)

            clone_cmd = [
                "git", "clone",
                "--depth", "1",
                "--branch", branch,
                git_url,
                clone_dir
            ]
            rc = run_command(clone_cmd)
            if rc != 0:
                print(f"  [test_ops] Failed to clone {git_url}. Skipping these sub-pkgs.", file=sys.stderr)
                all_passed = False
                continue

            # For each subdirectory in that repo, do a test run
            for (dep_name, subdir) in sub_pkgs:
                test_path = os.path.join(clone_dir, *subdir.split("/"))  # ensure cross-platform
                pyproj_file = os.path.join(test_path, "pyproject.toml")
                if not os.path.isdir(test_path):
                    print(f"  [test_ops][{dep_name}] Subdirectory '{subdir}' not found.", file=sys.stderr)
                    all_passed = False
                    continue
                if not os.path.isfile(pyproj_file):
                    print(f"  [test_ops][{dep_name}] No pyproject.toml in {test_path}. Skipping tests.", file=sys.stderr)
                    all_passed = False
                    continue

                # Now run tests
                print(f"  [test_ops][{dep_name}] Running tests in {test_path}")
                test_result = run_pytests(test_path, num_workers)
                details.append(test_result)
                if not test_result["success"]:
                    all_passed = False
    finally:
        if cleanup:
            shutil.rmtree(build_root, ignore_errors=True)
            print(f"[test_ops] Cleaned up temporary test directory: {build_root}")
            build_root = None

    return all_passed, build_root
