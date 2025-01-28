# soliloquy/ops/poetry_utils.py

import subprocess
import sys
from typing import List, Optional

def run_command(cmd: List[str], cwd: Optional[str] = None) -> int:
    """
    Runs the given command in the specified working directory.
    Returns the integer exit code (0 indicates success).

    We mask any PyPI tokens that start with 'pypi-' when printing.
    """
    # Build a safe-to-print version of the command, masking pypi- tokens
    safe_cmd = []
    for idx, arg in enumerate(cmd):
        if arg.startswith("pypi-"):
            # Mask the token
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
        return process.returncode
    except Exception as e:
        print(f"[poetry_utils] Error running command {cmd}: {e}", file=sys.stderr)
        return 1
