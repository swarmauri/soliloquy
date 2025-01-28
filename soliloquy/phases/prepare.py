# soliloquy/phases/prepare.py

import sys
from typing import Any

# Import the operations from their respective modules
from soliloquy.ops.version_ops import bulk_bump_or_set_version
from soliloquy.ops.lint_ops import run_ruff_lint
from soliloquy.ops.git_ops import git_commit_all_changes

def run_prepare(args: Any) -> None:
    """
    The 'prepare' phase:

      1. Bump or set version (recursively if requested)
      2. Lint + autofix
      3. Git commit changes

    This function expects to be called with an 'args' object that has:
      - args.file (optional, for a single pyproject.toml)
      - args.directory (optional, for a directory of packages or aggregator)
      - args.recursive (bool)
      - args.bump (string or None)
      - args.set_ver (string or None)
      - args.commit_msg (string)
      - possibly other lint-related flags if needed
    """

    # --------------------------------------------------
    # 1. Bump or set version
    # --------------------------------------------------
    if not args.bump and not args.set_ver:
        print("[prepare] No version operation specified. Skipping version update.")
    else:
        bulk_bump_or_set_version(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive,
            bump=args.bump,
            set_ver=args.set_ver
        )

    # --------------------------------------------------
    # 2. Lint + autofix
    # --------------------------------------------------
    # For demonstration, let's lint exactly one directory. 
    # If you want to lint multiple subdirectories, adapt accordingly.
    lint_dir = args.directory or "."
    # If you want to exit on lint errors, set exit_on_error=True below.
    # Here, let's keep it false so we can proceed to commit anyway.
    run_ruff_lint(directories=[lint_dir], fix=True, exit_on_error=False)

    # --------------------------------------------------
    # 3. Git commit
    # --------------------------------------------------
    commit_msg = getattr(args, "commit_msg", "chore: prepare changes")
    success = git_commit_all_changes(commit_msg)
    if not success:
        print("[prepare] Git commit failed or there were no changes to commit.")
        # Decide whether to sys.exit(1) or just log and proceed
        # sys.exit(1)

    print("[prepare] Complete.")
