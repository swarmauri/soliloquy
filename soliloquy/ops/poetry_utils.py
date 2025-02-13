# soliloquy/ops/poetry_utils.py

import subprocess
import sys
from typing import List, Optional, Tuple

def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Runs the given command in the specified working directory.

    Returns:
        A tuple (returncode, stdout, stderr) where:
            - returncode (int): The command's exit code (0 indicates success).
            - stdout (str): Captured standard output.
            - stderr (str): Captured standard error.
    
    We mask any PyPI tokens that start with 'pypi-' when printing.
    """
    # Build a safe-to-print version of the command, masking pypi- tokens.
    safe_cmd = []
    for arg in cmd:
        if arg.startswith("pypi-"):
            safe_cmd.append("pypi-****")
        else:
            safe_cmd.append(arg)

    print(f"[poetry_utils] Running command: {' '.join(safe_cmd)} (cwd={cwd or '.'})", flush=True)

    try:
        process = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False
        )
        return process.returncode, process.stdout, process.stderr
    except Exception as e:
        error_msg = f"Error running command {cmd}: {e}"
        print(f"[poetry_utils] {error_msg}", file=sys.stderr)
        return 1, "", error_msg
