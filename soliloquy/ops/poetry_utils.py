# soliloquy/ops/poetry_utils.py

import subprocess
import sys
from typing import List, Optional

def run_command(cmd: List[str], cwd: Optional[str] = None) -> int:
    """
    Runs the given command (list of strings) in the specified working directory.
    Returns the integer exit code (0 indicates success).

    Args:
        cmd: A list of command and arguments, e.g. ["poetry", "build"].
        cwd: An optional directory in which to run the command. Defaults to None (current dir).

    Example:
        exit_code = run_command(["poetry", "install"], cwd="/path/to/package")
        if exit_code != 0:
            print("Command failed!")
    """
    # Print the command for debugging
    print(f"[poetry_utils] Running command: {' '.join(cmd)} (cwd={cwd or '.'})", flush=True)
    try:
        process = subprocess.run(
            command_args,
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False
        )
        return process.returncode
    except Exception as e:
        print(f"[poetry_utils] Error running command {cmd}: {e}", file=sys.stderr)
        return 1