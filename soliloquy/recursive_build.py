import os
import sys
import tomlkit
from .poetry_ops import run_command
from .pyproject_ops import extract_path_dependencies, extract_git_dependencies
from .poetry_ops import find_pyproject_files

def recursive_build(file: str = None, directory: str = None, recursive: bool = False):
    """
    Recursively build packages based on path and/or git dependencies
    extracted from one or more pyproject.toml files.

    Steps:
      1. Identify which pyproject.toml files to process.
      2. Parse each pyproject.toml, checking 'package-mode'.
      3. If package-mode=true (or unspecified), build the root package itself.
      4. Gather path dependencies & build each local path package.
      5. Gather git dependencies (optional) and decide whether to build them.
    """
    # Step 1: Find all relevant pyproject.toml files
    try:
        pyproject_files = find_pyproject_files(
            file=file, directory=directory, recursive=recursive
        )
    except Exception as e:
        print(f"Error discovering pyproject files: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 2: For each discovered pyproject.toml
    for pyproject_path in pyproject_files:
        print(f"\nExamining '{pyproject_path}' ...")

        # Parse the doc using tomlkit
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                doc = tomlkit.parse(f.read())
        except Exception as e:
            print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
            continue  # or sys.exit(1)

        # Retrieve the [tool.poetry] table
        tool_poetry = doc.get("tool", {}).get("poetry", {})
        project_dir = os.path.dirname(pyproject_path)

        # Determine if it's package-mode or aggregator-mode
        # Default to 'True' if not specified (so it's buildable).
        is_package_mode = tool_poetry.get("package-mode", True)
        if isinstance(is_package_mode, bool):
            pass  # Good, we can use it directly
        else:
            # If someone used a string "false", we can interpret that
            if str(is_package_mode).lower() == "false":
                is_package_mode = False
            else:
                is_package_mode = True  # fallback

        package_name = tool_poetry.get("name")
        package_version = tool_poetry.get("version")

        if is_package_mode:
            # We consider it a normal package, so build the root package first
            print(f"Detected normal package '{package_name}' (version: {package_version}).")
            try:
                run_command(["poetry", "build"], cwd=project_dir)
            except Exception as e:
                print(f"Failed to build root package in {project_dir}: {e}", file=sys.stderr)
        else:
            # It's aggregator (monorepo) mode
            print("Detected 'monorepo aggregator' (package-mode=false). Skipping direct build of root.")

        # Step 4: Build local path dependencies
        path_deps = extract_path_dependencies(pyproject_path)
        if path_deps:
            print(f"Found {len(path_deps)} path dependencies in {pyproject_path}.")
            for sub_path in path_deps:
                full_path = os.path.join(project_dir, sub_path)
                sub_pyproject = os.path.join(full_path, "pyproject.toml")

                if os.path.isdir(full_path) and os.path.isfile(sub_pyproject):
                    print(f"Building local path dependency: {full_path}")
                    try:
                        run_command(["poetry", "build"], cwd=full_path)
                    except Exception as e:
                        print(f"Failed to build path dependency {full_path}: {e}", file=sys.stderr)
                else:
                    print(f"Skipping {full_path}: not a valid local package directory.")
        else:
            print(f"No local path dependencies found in {pyproject_path}.")

        # Step 5 (Optional): Gather and build Git dependencies
        git_deps = extract_git_dependencies(pyproject_path)
        if git_deps:
            print(f"Found {len(git_deps)} Git dependencies in {pyproject_path}.")

            # If you want to build them locally, you'd clone them and run "poetry build".
            # Otherwise, skip. Example pseudocode:
            for name, details in git_deps.items():
                git_url = details.get("git")
                if not git_url:
                    continue
                print(f"Detected git dependency '{name}' from {git_url}. (Skipping or cloning...)")
                # ...
        else:
            print(f"No Git dependencies found in {pyproject_path}.")
