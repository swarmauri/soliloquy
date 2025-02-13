# soliloquy/ops/poetry_utils.py

import subprocess
import sys
import threading
from typing import List, Optional, Tuple

def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Runs the given command in the specified working directory, streaming output live.
    
    Returns:
        A tuple (returncode, stdout, stderr) where:
            - returncode (int): The command's exit code.
            - stdout (str): Captured standard output.
            - stderr (str): Captured standard error.
    
    This function streams output line-by-line to the console while also capturing
    it for further processing.
    """
    # Build a safe-to-print version of the command, masking pypi- tokens.
    safe_cmd = [ "pypi-****" if arg.startswith("pypi-") else arg for arg in cmd ]
    print(f"[poetry_utils] Running command: {' '.join(safe_cmd)} (cwd={cwd or '.'})", flush=True)

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    stdout_lines = []
    stderr_lines = []

    def stream_reader(stream, output_list, print_func):
        # Read and print each line as it becomes available.
        for line in iter(stream.readline, ''):
            output_list.append(line)
            print_func(line, end='')  # end='' avoids double newlines
        stream.close()

    # Create threads for stdout and stderr
    stdout_thread = threading.Thread(target=stream_reader, args=(process.stdout, stdout_lines, sys.stdout.write))
    stderr_thread = threading.Thread(target=stream_reader, args=(process.stderr, stderr_lines, sys.stderr.write))

    stdout_thread.start()
    stderr_thread.start()

    # Wait for the threads to finish and then for the process to exit.
    stdout_thread.join()
    stderr_thread.join()
    returncode = process.wait()

    return returncode, ''.join(stdout_lines), ''.join(stderr_lines)
