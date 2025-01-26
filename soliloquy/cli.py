#!/usr/bin/env python3
"""
cli.py

Main CLI entry point, now using:
  - Command mapping for dispatch
  - Short and long flags for --file (-f), --dir (-d), --recursive (-R), etc.
  - Uniform file/directory handling
  - Optional recursive discovery of pyproject.toml files
"""

import argparse
import os
import sys
from typing import List

# Local modules
from soliloquy import poetry_ops
from soliloquy import version_ops
from soliloquy import remote_ops
from soliloquy import test_ops
from soliloquy import pyproject_ops


def resolve_targets(directory: str = None,
                    file: str = None,
                    recursive: bool = False,
                    default_filename: str = "pyproject.toml") -> List[str]:
    """
    Determine which pyproject.toml file(s) to operate on.

    - If `file` is specified, return just that file (if it exists).
    - Else if `directory` is specified:
        - If `recursive=True`, walk the directory and include every subdir
          containing a file named `default_filename`.
        - Otherwise, just return one file: <directory>/<default_filename>
    """
    if file:
        file_path = os.path.abspath(file)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Specified file does not exist: {file_path}")
        return [file_path]

    if directory:
        directory_path = os.path.abspath(directory)
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"Specified directory does not exist: {directory_path}")

        if recursive:
            matched = []
            for root, dirs, files in os.walk(directory_path):
                if default_filename in files:
                    matched.append(os.path.join(root, default_filename))
            if not matched:
                raise FileNotFoundError(
                    f"No '{default_filename}' files found recursively in {directory_path}"
                )
            return matched
        else:
            single_file = os.path.join(directory_path, default_filename)
            if not os.path.isfile(single_file):
                raise FileNotFoundError(f"No {default_filename} found in {directory_path}")
            return [single_file]

    # If neither file nor directory is provided, fallback or raise
    raise ValueError("Must provide either -f/--file or -d/--dir")


#------------------------------------------------------------------------------
# Command Handlers
#------------------------------------------------------------------------------

def handle_lock(args):
    try:
        targets = resolve_targets(args.dir, args.file, args.recursive)
        for t in targets:
            location = os.path.dirname(t)
            poetry_ops.poetry_lock(location)
    except Exception as e:
        print(f"Error in lock command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_install(args):
    try:
        targets = resolve_targets(args.dir, args.file, args.recursive)
        for t in targets:
            location = os.path.dirname(t)
            poetry_ops.poetry_install(
                location,
                extras=args.extras,
                with_dev=args.dev,
                all_extras=args.all_extras
            )
    except Exception as e:
        print(f"Error in install command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_build(args):
    # We see which sub-subcommand was chosen
    if args.build_cmd == "pkg":
        handle_build_pkg(args)
    elif args.build_cmd == "mono":
        handle_build_mono(args)
    else:
        print("Unknown build subcommand:", args.build_cmd)
        sys.exit(1)

def handle_build_pkg(args):
    """
    Handles 'cli build pkg' logic.
    Supports -f, -d, and optional -R.
    """
    from soliloquy import poetry_ops
    try:
        # This calls your existing "recursive_build" or a variation of it.
        poetry_ops.recursive_build(
            file=args.file,
            directory=args.dir,
            recursive=args.recursive
        )
    except Exception as e:
        print(f"Error in build pkg command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_build_mono(args):
    """
    Handles 'cli build mono' logic.
    Only supports -f (i.e., a single aggregator pyproject).
    """
    from soliloquy import poetry_ops
    try:
        # This calls a specialized function for monorepo aggregator building,
        # or reuses the same function if you'd like but with some constraints.
        poetry_ops.build_monorepo(file=args.file)
    except Exception as e:
        print(f"Error in build mono command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_version(args):
    # We renamed the argument to --file/-f for consistency
    try:
        version_ops.bump_or_set_version(
            pyproject_file=args.file,
            bump=args.bump,
            set_ver=args.set_ver
        )
    except Exception as e:
        print(f"Error in version command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_remote(args):
    if args.remote_cmd == "fetch":
        try:
            ver = remote_ops.fetch_remote_pyproject_version(
                git_url=args.git_url,
                branch=args.branch,
                subdirectory=args.subdir
            )
            if ver:
                print(f"Fetched remote version: {ver}")
            else:
                print("Failed to fetch remote version.")
        except Exception as e:
            print(f"Error in remote fetch command: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.remote_cmd == "update":
        try:
            success = remote_ops.update_and_write_pyproject(args.file, args.output)
            if not success:
                sys.exit(1)
        except Exception as e:
            print(f"Error in remote update command: {e}", file=sys.stderr)
            sys.exit(1)


def handle_test(args):
    # Run tests using pytest (with optional parallelism)
    try:
        poetry_ops.run_pytests(test_directory=args.dir, num_workers=args.num_workers)
    except Exception as e:
        print(f"Error in test command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_analyze(args):
    try:
        test_ops.analyze_test_file(
            file_path=args.file,
            required_passed=args.required_passed,
            required_skipped=args.required_skipped
        )
    except Exception as e:
        print(f"Error in analyze command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_pyproject(args):
    try:
        # For "pyproject" subcommand, we interpret --pyproject as a directory or file input
        # If you prefer short flags here, you can add -f or -d similarly
        targets = resolve_targets(directory=args.pyproject, file=None, recursive=False)
        pyproject_path = targets[0]

        print("Extracting dependencies from pyproject.toml ...")
        paths = pyproject_ops.extract_path_dependencies(pyproject_path)
        if paths:
            print("Local (path) dependencies:")
            print(", ".join(paths))
        else:
            print("No local path dependencies found.")

        git_deps = pyproject_ops.extract_git_dependencies(pyproject_path)
        if git_deps:
            print("\nGit dependencies:")
            for name, details in git_deps.items():
                print(f"{name}: {details}")
        else:
            print("No Git dependencies found.")

        if args.update_version:
            print(f"\nUpdating local dependency versions to {args.update_version} ...")
            pyproject_ops.update_dependency_versions(pyproject_path, args.update_version)
    except Exception as e:
        print(f"Error in pyproject command: {e}", file=sys.stderr)
        sys.exit(1)


def handle_publish(args):
    try:
        poetry_ops.poetry_publish(
            file=args.file,
            directory=args.dir,
            recursive=args.recursive,
            username=args.username,
            password=args.password
        )
    except Exception as e:
        print(f"Error in publish command: {e}", file=sys.stderr)
        sys.exit(1)

def handle_lint(args):
    """
    Dispatch linting tasks to poetry_ops.poetry_ruff_lint.
    """
    try:
        # If the user provided -d/--dir, we'll pass that to poetry_ruff_lint
        directory = args.dir or "."
        poetry_ops.poetry_ruff_lint(directory=directory, fix=args.fix)
    except Exception as e:
        print(f"Error in lint command: {e}", file=sys.stderr)
        sys.exit(1)


#------------------------------------------------------------------------------
# Main Entry Point with Subparser & Command Mapping
#------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A CLI for managing a Python monorepo with multiple standalone packages."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # lock
    lock_parser = subparsers.add_parser("lock", help="Generate a poetry.lock file")
    lock_parser.add_argument("-d", "--dir", type=str, help="Directory containing pyproject.toml")
    lock_parser.add_argument("-f", "--file", type=str, help="Explicit path to a pyproject.toml file")
    lock_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files")
    
    # install
    install_parser = subparsers.add_parser("install", help="Install dependencies")
    install_parser.add_argument("-d", "--dir", type=str, help="Directory containing pyproject.toml")
    install_parser.add_argument("-f", "--file", type=str, help="Explicit path to a pyproject.toml file")
    install_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files")
    install_parser.add_argument("--extras", type=str, help="Extras to include (e.g. 'full')")
    install_parser.add_argument("--dev", action="store_true", help="Include dev dependencies")
    install_parser.add_argument("--all-extras", action="store_true", help="Include all extras")
    
    #-----------------------------------------------------------------
    # build
    #-----------------------------------------------------------------
    build_parser = subparsers.add_parser("build", help="Build packages")
    build_subparsers = build_parser.add_subparsers(dest="build_cmd", required=True)

    # build pkg
    pkg_parser = build_subparsers.add_parser("pkg", help="Build a single or multiple packages")
    pkg_parser.add_argument("-f", "--file", type=str, help="Path to a pyproject.toml")
    pkg_parser.add_argument("-d", "--dir", type=str, help="Directory containing pyproject.toml(s)")
    pkg_parser.add_argument("-R", "--recursive", action="store_true",
                            help="Recursively find pyproject.toml files in directory mode")
    # The function that handles 'build pkg'
    pkg_parser.set_defaults(func=handle_build_pkg)

    # build mono
    mono_parser = build_subparsers.add_parser("mono", help="Build monorepo aggregator only (requires -f).")
    mono_parser.add_argument("-f", "--file", type=str, required=True,
                             help="Path to a monorepo aggregator pyproject.toml (with package-mode=false)")
    # The function that handles 'build mono'
    mono_parser.set_defaults(func=handle_build_mono)
    
    # version
    version_parser = subparsers.add_parser("version", help="Bump or set package version")
    # Instead of a positional argument, we now use -f/--file:
    version_parser.add_argument("-f", "--file", required=True, help="Path to the pyproject.toml file")
    vgroup = version_parser.add_mutually_exclusive_group(required=True)
    vgroup.add_argument("--bump", choices=["major", "minor", "patch", "finalize"],
                        help="Bump the version (e.g. patch, major, minor, finalize)")
    vgroup.add_argument("--set", dest="set_ver", help="Explicit version to set (e.g. 2.0.0.dev1)")
    
    # remote
    remote_parser = subparsers.add_parser("remote", help="Remote operations for Git dependencies")
    remote_subparsers = remote_parser.add_subparsers(dest="remote_cmd", required=True)
    
    fetch_parser = remote_subparsers.add_parser("fetch", help="Fetch version from remote GitHub pyproject.toml")
    fetch_parser.add_argument("--git-url", type=str, required=True, help="GitHub repository URL")
    fetch_parser.add_argument("--branch", type=str, default="main", help="Branch name (default: main)")
    fetch_parser.add_argument("--subdir", type=str, default="", help="Subdirectory for pyproject.toml")
    
    update_parser = remote_subparsers.add_parser("update", help="Update local pyproject.toml with remote versions")
    # Use short/long for file & output
    update_parser.add_argument("-f", "--file", required=True, help="Path to the local pyproject.toml")
    update_parser.add_argument("-o", "--output", help="Optional output file path (defaults to overwriting the input)")

    # test
    test_parser = subparsers.add_parser("test", help="Run tests using pytest")
    test_parser.add_argument("-d", "--dir", type=str, default=".", help="Directory to run tests (default: .)")
    test_parser.add_argument("--num-workers", type=int, default=1, help="Number of parallel workers")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze test results from a JSON file")
    analyze_parser.add_argument("-f", "--file", help="Path to the JSON file with test results", required=True)
    analyze_parser.add_argument("--required-passed", type=str, help="Threshold for passed tests (e.g. 'gt:75')")
    analyze_parser.add_argument("--required-skipped", type=str, help="Threshold for skipped tests (e.g. 'lt:20')")

    # pyproject
    pyproject_parser = subparsers.add_parser("pyproject", help="Operate on pyproject.toml dependencies")
    pyproject_parser.add_argument("--pyproject", required=True, help="Path (or directory) to pyproject.toml")
    pyproject_parser.add_argument("--update-version", type=str, help="Update local dependency versions")

    # publish
    publish_parser = subparsers.add_parser("publish", help="Publish package(s) to PyPI")
    publish_parser.add_argument("-f", "--file", type=str, help="Path to a specific pyproject.toml")
    publish_parser.add_argument("-d", "--dir", type=str, help="Directory containing pyproject.toml(s)")
    publish_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files")
    publish_parser.add_argument("--username", type=str, help="PyPI username")
    publish_parser.add_argument("--password", type=str, help="PyPI password")


    # --------------------------------------------------
    # lint
    # --------------------------------------------------
    lint_parser = subparsers.add_parser("lint", help="Run Ruff lint checks (and optionally autofix).")
    lint_parser.add_argument("-d", "--dir", type=str,
                             help="Directory to lint (default: current directory).")
    lint_parser.add_argument("--fix", action="store_true",
                             help="Apply autofixes using 'ruff check --fix'.")

    # Map subcommands to handler functions
    COMMANDS = {
        "lock": handle_lock,
        "install": handle_install,
        "build": handle_build,
        "version": handle_version,
        "remote": handle_remote,
        "test": handle_test,
        "analyze": handle_analyze,
        "pyproject": handle_pyproject,
        "publish": handle_publish,
        "lint": handle_lint
    }

    args = parser.parse_args()
    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
