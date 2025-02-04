# soliloquy/ops/lint_ops.py

import os
import sys
import subprocess
from typing import List, Optional

def run_ruff_lint(
    directories: Optional[List[str]] = None,
    fix: bool = True,
    exit_on_error: bool = False
) -> bool:
    """
    Runs Ruff lint checks on one or more directories.

    :param directories: A list of directory paths to lint. If None or empty,
                        defaults to the current directory.
    :param fix: If True, pass '--fix' to Ruff to automatically fix issues.
    :param exit_on_error: If True, raise SystemExit on any error (non-zero return).
    :return: True if lint passed (0 exit code), False otherwise.
    """
    if not directories:
        directories = ["."]
    directories = [os.path.abspath(d) for d in directories]

    # Build the Ruff command. Example: ruff check <dir1> <dir2> ...
    cmd = ["ruff", "check"] + directories
    if fix:
        cmd.append("--fix")

    print(f"[lint_ops] Running: {' '.join(cmd)}", flush=True)

    # Run the command
    process = subprocess.run(cmd, capture_output=True, text=True)
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    success = (process.returncode == 0)

    if not success:
        msg = f"[lint_ops] Ruff linting failed with exit code {process.returncode}."
        if exit_on_error:
            # Raise SystemExit or a custom exception
            print(msg, file=sys.stderr)
            sys.exit(process.returncode)
        else:
            print(msg, file=sys.stderr)

    return success


def lint_directory(
    directory: str = ".",
    fix: bool = False,
    exit_on_error: bool = True
) -> bool:
    """
    Convenience function to lint a single directory with Ruff.
    """
    return run_ruff_lint(
        directories=[directory],
        fix=fix,
        exit_on_error=exit_on_error
    )
