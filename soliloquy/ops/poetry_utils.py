# soliloquy/ops/poetry_utils.py

import subprocess
import sys
import threading
import queue
from typing import List, Optional, Tuple

def _stream_reader(pipe, q, print_func):
    """
    Reads lines from the given pipe, prints them via print_func,
    and puts them into the provided queue.
    """
    try:
        for line in iter(pipe.readline, ''):
            print_func(line, end='')  # Stream line immediately
            q.put(line)
    finally:
        pipe.close()

def run_command(cmd: List[str], cwd: Optional[str] = None, stream: bool = False) -> Tuple[int, str, str]:
    """
    Runs the given command in the specified working directory.
    
    Args:
        cmd: Command to run as a list of strings.
        cwd: Working directory in which to run the command.
        stream: If True, stream stdout and stderr to sys.stdout and sys.stderr as they are produced.
        
    Returns:
        A tuple (returncode, stdout, stderr) where:
            - returncode (int): The exit code of the command.
            - stdout (str): Captured standard output.
            - stderr (str): Captured standard error.
    
    Any tokens starting with 'pypi-' are masked in the printed command.
    """
    # Create a safe-to-print version of the command
    safe_cmd = [("pypi-****" if arg.startswith("pypi-") else arg) for arg in cmd]
    print(f"[poetry_utils] Running command: {' '.join(safe_cmd)} (cwd={cwd or '.'})", flush=True)

    if stream:
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        q_stdout = queue.Queue()
        q_stderr = queue.Queue()

        stdout_thread = threading.Thread(target=_stream_reader, args=(process.stdout, q_stdout, sys.stdout.write))
        stderr_thread = threading.Thread(target=_stream_reader, args=(process.stderr, q_stderr, sys.stderr.write))
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to complete and the threads to finish
        stdout_thread.join()
        stderr_thread.join()
        retcode = process.wait()

        # Collect output from the queues
        stdout_lines = []
        while not q_stdout.empty():
            stdout_lines.append(q_stdout.get())
        stderr_lines = []
        while not q_stderr.empty():
            stderr_lines.append(q_stderr.get())
        return retcode, ''.join(stdout_lines), ''.join(stderr_lines)
    else:
        # Use subprocess.run to capture output after the command finishes
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False
        )
        return result.returncode, result.stdout, result.stderr
