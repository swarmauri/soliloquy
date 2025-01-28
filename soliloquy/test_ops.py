#!/usr/bin/env python3
"""
test_ops.py

Implements new test modes for a monorepo:
  - run_monorepo_tests: one unified pytest run
  - run_subpackage_tests: run pytest in each subpackage
  - (single-package tests are already handled by poetry_ops.run_pytests)
"""

import os
import sys
import glob
import subprocess
from typing import List

from .poetry_ops import run_pytests   # Your existing function
from .pyproject_ops import find_pyproject_files, extract_path_dependencies
# or from .pyproject_ops import ... if you prefer

def run_monorepo_tests(root_dir: str, num_workers: int = 1):
    """
    Runs a single pytest invocation at the top level.

    This typically discovers tests in all subdirectories automatically,
    assuming standard pytest discovery rules.
    """
    print(f"[monorepo] Running one pytest run from {root_dir} ...")
    run_pytests(test_directory=root_dir, num_workers=num_workers)

def run_subpackage_tests(root_dir: str, num_workers: int = 1):
    """
    Discovers subpackages and runs a separate pytest invocation in each.
    If there's an aggregator pyproject.toml with path dependencies, we can use that
    for subpackage discovery. Otherwise, do something like find all 'pyproject.toml' 
    that have 'package-mode=true', etc.
    """
    print(f"[subpackages] Searching for subpackages in {root_dir} ...")

    # 1) Possibly look for an aggregator in the specified directory
    #    If none found, fallback to a recursive search for "pyproject.toml"
    #    that have 'package-mode' or contain tests, etc.
    try:
        aggregator_files = find_pyproject_files(
            file=None, directory=root_dir, recursive=False
        )
        aggregator_pyproject = aggregator_files[0] if aggregator_files else None
    except Exception:
        aggregator_pyproject = None

    subpackage_dirs: List[str] = []

    if aggregator_pyproject:
        print(f"Aggregator file found: {aggregator_pyproject}")
        # Extract local path deps from aggregator
        path_deps = extract_path_dependencies(aggregator_pyproject)
        aggregator_dir = os.path.dirname(aggregator_pyproject)

        for p in path_deps:
            full_subpkg_path = os.path.join(aggregator_dir, p)
            pyproj = os.path.join(full_subpkg_path, "pyproject.toml")
            if os.path.isdir(full_subpkg_path) and os.path.isfile(pyproj):
                subpackage_dirs.append(full_subpkg_path)
    else:
        # If no aggregator, do a fallback: search all pyproject.toml in subdirs
        # that are not the root, and treat them as subpackages
        # (e.g. skip aggregator or non-package-mode).
        all_pyprojects = find_pyproject_files(
            file=None, directory=root_dir, recursive=True
        )
        root_abs = os.path.abspath(root_dir)

        for pyproj in all_pyprojects:
            if os.path.dirname(pyproj) == root_abs:
                # This is the same dir as root_dir, skip aggregator if any
                continue
            subpackage_dirs.append(os.path.dirname(pyproj))

    if not subpackage_dirs:
        print("No subpackages found. Exiting.")
        return

    print(f"\nFound {len(subpackage_dirs)} subpackages. Testing each individually ...")

    failure_count = 0
    for sub_dir in subpackage_dirs:
        print(f"\n=== Testing subpackage: {sub_dir} ===")
        try:
            run_pytests(test_directory=sub_dir, num_workers=num_workers)
        except SystemExit as e:
            # If your run_pytests() might do sys.exit(...) on errors,
            # handle that here:
            failure_count += 1
            print(f"Tests FAILED in {sub_dir}", file=sys.stderr)

    if failure_count > 0:
        print(f"\nFAIL: {failure_count} subpackages had test failures.")
        # You may prefer sys.exit(1) here:
        sys.exit(1)
    else:
        print("\nAll subpackages passed successfully!")
