# soliloquy/ops/format_ops.py

import os
import sys
import subprocess
from typing import List, Optional

def run_ruff_format(
    directories: Optional[List[str]] = None,
    exit_on_error: bool = False
) -> bool:
    """
    Runs Ruff's formatting command on one or more directories.

    :param directories: A list of directory paths to format. If None or empty,
                        defaults to the current directory.
    :param exit_on_error: If True, raises SystemExit on any error (non-zero return).
    :return: True if formatting succeeded (i.e. Ruff returns 0), False otherwise.
    """
    if not directories:
        directories = ["."]
    directories = [os.path.abspath(d) for d in directories]

    # Build the Ruff command using the `format` subcommand.
    cmd = ["ruff", "format"] + directories

    print(f"[format_ops] Running: {' '.join(cmd)}", flush=True)

    # Run the command and capture its output.
    process = subprocess.run(cmd, capture_output=True, text=True)
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    success = (process.returncode == 0)

    if not success:
        msg = f"[format_ops] Ruff formatting failed with exit code {process.returncode}."
        if exit_on_error:
            print(msg, file=sys.stderr)
            sys.exit(process.returncode)
        else:
            print(msg, file=sys.stderr)

    return success


def format_directory(
    directory: str = ".",
    exit_on_error: bool = False
) -> bool:
    """
    Convenience function to format a single directory with Ruff.

    :param directory: Directory path to format.
    :param exit_on_error: If True, raises SystemExit on any error (non-zero return).
    :return: True if formatting succeeded, False otherwise.
    """
    return run_ruff_format(
        directories=[directory],
        exit_on_error=exit_on_error
    )
