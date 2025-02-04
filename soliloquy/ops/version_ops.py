# soliloquy/ops/version_ops.py

import os
from packaging.version import Version, InvalidVersion
from tomlkit import parse, dumps

# Import your existing "find_pyproject_files" or define it in pyproject_ops:
from soliloquy.ops.pyproject_ops import find_pyproject_files


def read_pyproject_version(file_path: str) -> str:
    """
    Reads the current version from the given pyproject.toml file.

    Returns:
      The version string (e.g. '1.2.3.dev1').

    Raises:
      FileNotFoundError: if the file is missing.
      KeyError: if [tool.poetry.version] doesn't exist.
      ValueError: if the file cannot be parsed correctly.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        doc = parse(content)
    except Exception as e:
        raise ValueError(f"Could not parse TOML from {file_path}: {e}") from e

    # Attempt to retrieve version from [tool.poetry]
    try:
        return doc["tool"]["poetry"]["version"]
    except KeyError:
        raise KeyError(f"No version found under [tool.poetry] in {file_path}")


def write_pyproject_version(file_path: str, new_version: str) -> None:
    """
    Writes the given new_version string (e.g. '1.2.3.dev2') into pyproject.toml
    at [tool.poetry].version.

    Raises:
      FileNotFoundError: if the file is missing.
      ValueError: if the file cannot be parsed correctly or structure is invalid.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = parse(f.read())
    except Exception as e:
        raise ValueError(f"Could not parse TOML from {file_path}: {e}") from e

    if "tool" not in doc or "poetry" not in doc["tool"]:
        raise ValueError(f"Invalid structure in {file_path}; no [tool.poetry] table.")

    doc["tool"]["poetry"]["version"] = new_version

    # Write updated file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dumps(doc))
    except Exception as e:
        raise ValueError(f"Failed writing updated pyproject.toml to {file_path}: {e}") from e


def bump_version(current_version: str, bump_type: str) -> str:
    """
    Bumps the given current_version using one of:
      - 'major' -> X+1.0.0.dev1
      - 'minor' -> X.Y+1.0.dev1
      - 'patch' -> if dev, increment dev number; else X.Y.Z+1.dev1
      - 'finalize' -> remove .devN if present

    Returns the new version string.

    Raises:
      ValueError: if the version is invalid or the bump operation is invalid.
    """
    try:
        ver = Version(current_version)
    except InvalidVersion as e:
        raise ValueError(f"Invalid current version '{current_version}': {e}") from e

    is_dev = (ver.dev is not None)
    major, minor, patch = ver.release

    if bump_type == "finalize":
        if is_dev:
            # remove dev portion
            return f"{major}.{minor}.{patch}"
        else:
            raise ValueError("Current version is already final; nothing to finalize.")

    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
        return f"{major}.{minor}.{patch}.dev1"

    elif bump_type == "minor":
        minor += 1
        patch = 0
        return f"{major}.{minor}.{patch}.dev1"

    elif bump_type == "patch":
        if is_dev:
            # e.g. 1.2.3.dev2 -> 1.2.3.dev3
            new_dev = ver.dev + 1
            return f"{major}.{minor}.{patch}.dev{new_dev}"
        else:
            # e.g. 1.2.3 -> 1.2.4.dev1
            patch += 1
            return f"{major}.{minor}.{patch}.dev1"

    else:
        raise ValueError("bump_type must be one of 'major', 'minor', 'patch', 'finalize'.")


def validate_new_version_is_not_lower(current_version: str, new_version: str) -> None:
    """
    Raises ValueError if new_version is lower than current_version.
    Otherwise, returns None (success).
    """
    try:
        cur_ver = Version(current_version)
        tgt_ver = Version(new_version)
    except InvalidVersion as e:
        raise ValueError(f"Invalid version provided: {e}") from e

    if tgt_ver < cur_ver:
        raise ValueError("You cannot bump the version downwards; target version must be >= current version.")


def bulk_bump_or_set_version(
    file: str = None,
    directory: str = None,
    recursive: bool = False,
    bump: str = None,
    set_ver: str = None
) -> None:
    """
    Finds pyproject.toml files via file/directory/recursive logic,
    then for each:
      - reads the current version,
      - either bumps or sets it,
      - checks that new version is not lower,
      - writes the updated version back.

    :param file: Path to a single pyproject.toml (standalone).
    :param directory: Directory containing one or more pyproject.toml.
    :param recursive: Whether to find pyproject files recursively in directory.
    :param bump: 'major', 'minor', 'patch', or 'finalize' (if set).
    :param set_ver: explicit version string to set (if set).
    """
    if not bump and not set_ver:
        print("[version_ops] No bump or set_ver specified. Skipping version update.")
        return

    try:
        pyproject_files = find_pyproject_files(file, directory, recursive)
    except Exception as e:
        raise RuntimeError(f"Error discovering pyproject files: {e}") from e

    for pyproj in pyproject_files:
        print(f"[version_ops] Updating version in {pyproj} ...")

        current_ver = read_pyproject_version(pyproj)

        if bump:
            new_ver = bump_version(current_ver, bump)
        else:
            # set_ver path
            new_ver = set_ver

        # Validate new version >= current version
        validate_new_version_is_not_lower(current_ver, new_ver)

        # Finally write to file
        write_pyproject_version(pyproj, new_ver)

        print(f"    {current_ver} -> {new_ver}")
