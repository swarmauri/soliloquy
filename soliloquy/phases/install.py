# soliloquy/phases/install.py

import sys
from typing import Any

from soliloquy.ops.lock_ops import lock_packages
from soliloquy.ops.install_ops import install_packages

def run_install(args: Any) -> None:
    """
    The 'install' phase:
      1. Lock
      2. Install

    Expects 'args' with:
      - file/directory/recursive
      - Possibly other flags if needed
    """

    print("[install] Locking packages...")
    lock_ok = lock_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not lock_ok:
        print("[install] 'poetry lock' failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("[install] Installing packages...")
    install_ok = install_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not install_ok:
        print("[install] 'poetry install' failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("[install] Completed successfully.")
