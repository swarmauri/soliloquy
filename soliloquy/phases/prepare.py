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
      2. Lint + autofix (if enabled by CLI flags)
      3. Git commit changes

    Expects args to have:
      - args.file (optional)
      - args.directory (optional)
      - args.recursive (bool)
      - args.bump (str or None)
      - args.set_ver (str or None)
      - args.commit_msg (str)
      - args.lint_fix (bool) -- whether to auto-fix lint errors
      - args.lint_no_exit (bool) -- whether to NOT exit on lint errors
      ... plus other flags.
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
    lint_dir = args.directory or "."
    # Use the new CLI flags to determine lint behavior:
    lint_fix = args.lint_fix  # defaults to False if not set
    exit_on_error = not args.lint_no_exit  # if --lint-no-exit is set, then exit_on_error is False

    run_ruff_lint(directories=[lint_dir], fix=lint_fix, exit_on_error=exit_on_error)

    # --------------------------------------------------
    # 3. Git commit
    # --------------------------------------------------
    commit_msg = getattr(args, "commit_msg", "chore: prepare changes")
    success = git_commit_all_changes(commit_msg)
    if not success:
        print("[prepare] Git commit failed or there were no changes to commit.")
        # Optionally, handle the failure (e.g., sys.exit(1))

    print("[prepare] Complete.")
