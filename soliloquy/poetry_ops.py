#!/usr/bin/env python3
"""
poetry_ops.py

Key changes:
  - Removed install_poetry()
  - run_command now uses shell=False and an array of arguments
  - If reading/writing pyproject, switch to tomlkit (if needed)
"""
from typing import List, Optional, Dict, Any, Tuple
import os
import subprocess
import sys
import tempfile
import shutil
import tomlkit
from tomlkit import parse
from .pyproject_ops import extract_path_dependencies, extract_git_dependencies, find_pyproject_files

def run_command(command_args, cwd=None):
    """
    Run a shell command (as a list of args) with shell=False,
    capturing output. Raises CalledProcessError on failure.
    """
    try:
        result = subprocess.run(
            command_args,
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False
        )
        if result.stdout:
            print(result.stdout, end="")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr}", file=sys.stderr)
        sys.exit(e.returncode)

def poetry_lock(location):
    """
    Run 'poetry lock' in the specified location (directory).
    """
    print(f"Generating poetry.lock in {location}...")
    run_command(["poetry", "lock"], cwd=location)


def poetry_install(location, extras=None, with_dev=False, all_extras=False):
    """
    Run 'poetry install' in the specified location.
    """
    print(f"Installing dependencies in {location}...")
    command = ["poetry", "install", "--no-cache", "-vv"]
    if all_extras:
        command.append("--all-extras")
    if extras:
        for e in extras.split(","):
            command.extend(["--extras", e.strip()])
    if with_dev:
        command.extend(["--with", "dev"])
    run_command(command, cwd=location)


def extract_path_dependencies(pyproject_path):
    """
    Example reading with tomlkit instead of toml.
    """
    print(f"Extracting path dependencies from {pyproject_path}...")
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        sys.exit(1)

    deps = doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
    path_deps = [
        v["path"]
        for v in deps.values()
        if isinstance(v, dict) and "path" in v
    ]
    return path_deps

def run_pytests(test_directory=".", num_workers=1):
    """
    Run pytest in the specified directory.
    """
    command = ["poetry", "run", "pytest"]
    if num_workers > 1:
        command.extend(["-n", str(num_workers)])
    print(f"Running tests in '{test_directory}' with command: {' '.join(command)}")
    run_command(command, cwd=test_directory)


def poetry_ruff_lint(directory=".", fix=False):
    """
    Runs Ruff lint checks in the specified directory.
    If fix=True, also pass --fix to autofix issues.

    :param directory: The directory to lint (defaults to '.')
    :param fix: Whether to run with --fix (autofixing) enabled.
    :param cwd: The current working directory to run the command in (defaults to None)
    """
    # Construct the base command: 'poetry run ruff check <dir>'
    command = ["poetry", "run", "ruff", "check", directory]
    if fix:
        command.append("--fix")

    print(f"Running Ruff on '{directory}' (fix={fix}) with cwd='{directory}'...")
    run_command(command, cwd=directory)


def build_monorepo(
    file: str,
    build_dir: str = None,
    cleanup: bool = True
):
    """
    Build a 'monorepo aggregator' pyproject.toml that has 'package-mode=false'
    by:
      1) Building all local path dependencies
      2) Cloning and building Git-based dependencies
      3) Moving the resulting dist artifacts into build_dir (if provided).

    :param file: Path to the aggregator pyproject.toml
    :param build_dir: If provided, we place cloned Git repos AND final build
                      artifacts here. If None, we use a temp folder for cloning
                      but still place final artifacts there.
    :param cleanup: Whether to remove our build_dir if it’s a temp folder.
    """
    import os
    import tempfile
    import shutil
    from typing import Dict, Tuple, List
    import glob

    from .pyproject_ops import extract_path_dependencies, extract_git_dependencies
    import tomlkit

    aggregator_path = os.path.abspath(file)
    if not os.path.isfile(aggregator_path):
        raise FileNotFoundError(f"Monorepo aggregator file not found: {aggregator_path}")

    print(f"Building monorepo aggregator from: {aggregator_path}")

    with open(aggregator_path, "r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())

    tool_poetry = doc.get("tool", {}).get("poetry", {})
    package_mode = tool_poetry.get("package-mode", True)
    if package_mode is not False:
        print("Warning: 'package-mode=false' not found or set. Proceeding as aggregator, but be aware.")

    aggregator_dir = os.path.dirname(aggregator_path)

    # ------------------------------------------------------
    # Helper function to build a project & then move its dist
    # artifacts into a subfolder under build_root.
    # ------------------------------------------------------
    def build_and_collect_artifacts(project_path: str, build_root: str):
        # Run 'poetry build' inside project_path
        run_command(["poetry", "build"], cwd=project_path)

        # dist/ subfolder inside that project
        dist_folder = os.path.join(project_path, "dist")
        if not os.path.isdir(dist_folder):
            return  # Might be an error or something, but let's just skip.

        # For neatness, name the subfolder after the project itself:
        project_name = os.path.basename(os.path.normpath(project_path))
        # e.g. build_root/mypackage
        target_folder = os.path.join(build_root, project_name)
        os.makedirs(target_folder, exist_ok=True)

        # Move any wheels/sdists to the target_folder
        for artifact in glob.glob(os.path.join(dist_folder, "*")):
            artifact_name = os.path.basename(artifact)
            dest_file = os.path.join(target_folder, artifact_name)
            print(f"Moving {artifact} -> {dest_file}")
            shutil.move(artifact, dest_file)

        # Optionally remove the now-empty dist folder:
        shutil.rmtree(dist_folder, ignore_errors=True)

    # ------------------------------------------------------
    # Decide how to create or re-use build_root
    # ------------------------------------------------------
    created_temp_dir = False
    if build_dir:
        build_root = os.path.abspath(build_dir)
        os.makedirs(build_root, exist_ok=True)
        print(f"Using user-specified build directory: {build_root}")
    else:
        build_root = tempfile.mkdtemp(prefix="mono_build_")
        created_temp_dir = True
        print(f"Using temporary directory for clones: {build_root}")

    # ------------------------------------------------------
    # 1) Build Local Path Dependencies
    # ------------------------------------------------------
    path_deps = extract_path_dependencies(aggregator_path)
    if path_deps:
        print(f"\nFound {len(path_deps)} local path dependencies. Building each ...")
        for path_rel in path_deps:
            sub_path = os.path.join(aggregator_dir, path_rel)
            pyproj_file = os.path.join(sub_path, "pyproject.toml")

            if not os.path.isdir(sub_path):
                print(f"Skipping '{path_rel}': directory not found at {sub_path}.")
                continue
            if not os.path.isfile(pyproj_file):
                print(f"Skipping '{sub_path}': no pyproject.toml found.")
                continue

            print(f"Building local path dependency in {sub_path} ...")
            try:
                build_and_collect_artifacts(sub_path, build_root)
            except Exception as e:
                print(f"Failed to build local path dependency {sub_path}: {e}")
    else:
        print("No local path dependencies found to build.")

    # ------------------------------------------------------
    # 2) Build Git Dependencies
    # ------------------------------------------------------
    git_deps = extract_git_dependencies(aggregator_path)
    if not git_deps:
        print("No Git dependencies found. Done.")
        # Possibly remove the build_root if it's temp and cleanup is True
        if created_temp_dir and cleanup:
            shutil.rmtree(build_root, ignore_errors=True)
            print(f"Cleaned up temporary directory: {build_root}")
        else:
            if not created_temp_dir:
                print(f"User-specified build directory left intact: {build_root}")
            else:
                print(f"Temporary build directory not removed: {build_root} (cleanup=False).")
        return

    print(f"\nFound {len(git_deps)} Git dependencies to build.")
    grouped_deps: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}

    for dep_name, details in git_deps.items():
        git_url = details.get("git")
        branch = details.get("branch", "main")
        subdir = details.get("subdirectory", ".")
        key = (git_url, branch)

        if key not in grouped_deps:
            grouped_deps[key] = []
        grouped_deps[key].append((dep_name, subdir))

    # Clone & build each grouping:
    try:
        for (git_url, branch), sub_pkgs in grouped_deps.items():
            print(f"\n---\nCloning {git_url} (branch: {branch}) to build {len(sub_pkgs)} sub-packages.")

            clone_dir_name = branch.replace("/", "-") + "_clone"
            clone_dir = os.path.join(build_root, clone_dir_name)

            clone_cmd = [
                "git", "clone",
                "--depth", "1",
                "--branch", branch,
                git_url,
                clone_dir
            ]

            try:
                run_command(clone_cmd)
            except Exception as e:
                print(f"Failed to clone {git_url}: {e}")
                continue

            # Build each subdirectory in the newly cloned repo
            for (dep_name, subdir) in sub_pkgs:
                sub_path = os.path.join(clone_dir, subdir)
                pyproj_file = os.path.join(sub_path, "pyproject.toml")

                if not os.path.isdir(sub_path):
                    print(f"[{dep_name}] Subdirectory '{subdir}' not found.")
                    continue
                if not os.path.isfile(pyproj_file):
                    print(f"[{dep_name}] No pyproject.toml in {sub_path}. Skipping.")
                    continue

                print(f"[{dep_name}] Building package in {sub_path}")
                try:
                    build_and_collect_artifacts(sub_path, build_root)
                except Exception as e:
                    print(f"[{dep_name}] Failed to build: {e}")

        print("\nAll local path & Git sub-packages processed.")
    finally:
        if created_temp_dir and cleanup:
            shutil.rmtree(build_root, ignore_errors=True)
            print(f"Cleaned up temporary directory: {build_root}")
        else:
            if not created_temp_dir:
                print(f"User-specified build directory left intact: {build_root}")
            else:
                print(f"Temporary build directory not removed: {build_root} (cleanup=False).")


def poetry_publish(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    username: str = None,
    password: str = None
):
    """
    Builds and publishes packages to PyPI (or another configured repository).

    You can specify one of:
      - file=<path to pyproject.toml>
      - directory=<path to directory containing pyproject.toml>
      - directory=<path> + recursive=True to walk subdirectories

    :param file: Explicit path to a pyproject.toml file.
    :param directory: Path to a directory that has (or contains) a pyproject.toml.
    :param recursive: If True, search subdirectories for pyproject.toml files.
    :param username: PyPI username (optional). If not provided, rely on Poetry config or interactive prompt.
    :param password: PyPI password (optional).
    """

    username = username or os.environ.get("POETRY_PYPI_USERNAME")
    password = password or os.environ.get("POETRY_PYPI_PASSWORD")

    try:
        pyproject_files = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        print(f"Error discovering pyproject files: {e}", file=sys.stderr)
        sys.exit(1)

    for pyproj in pyproject_files:
        project_dir = os.path.dirname(pyproj)
        print(f"Publishing package from {project_dir} ...")

        # 1. Build the package
        try:
            run_command(["poetry", "build"], cwd=project_dir)
        except Exception as e:
            print(f"Failed to build package in {project_dir}: {e}", file=sys.stderr)
            sys.exit(1)

        # 2. Publish the package
        publish_cmd = ["poetry", "publish"]
        # If you want verbose output, you can add ["-vv"] or similar
        if username and password:
            publish_cmd.extend(["--username", username, "--password", password])
        # If you have a custom repository name, you can also add --repository <repo>

        try:
            run_command(publish_cmd, cwd=project_dir)
        except Exception as e:
            print(f"Failed to publish package in {project_dir}: {e}", file=sys.stderr)
            sys.exit(1)