# soliloquy/phases/prepare.py

import sys
from typing import Any

# Import the operations from their respective modules
from soliloquy.ops.version_ops import bulk_bump_or_set_version
from soliloquy.ops.lint_ops import run_ruff_lint
from soliloquy.ops.format_ops import run_ruff_format
from soliloquy.ops.git_ops import git_commit_all_changes

def run_prepare(args: Any) -> None:
    """
    The 'prepare' phase:
      1. Bump or set version (recursively if requested)
      2. Lint + autofix (if enabled)
      3. Format code (if enabled)
      4. Git commit changes

    Expects args to have:
      - args.file (optional)
      - args.directory (optional)
      - args.recursive (bool)
      - args.bump (str or None)
      - args.set_ver (str or None)
      - args.commit_msg (str)
      - args.lint_fix (bool) -- whether to auto-fix lint errors
      - args.lint_no_exit (bool) -- whether to NOT exit on lint errors
      - args.disable_lint (bool) -- if True, skip the linting step
      - args.disable_format (bool) -- if True, skip the formatting step
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
    if not getattr(args, "disable_lint", False):
        lint_dir = args.directory or "."
        # Use the CLI flags (or default values) to control lint behavior:
        lint_fix = getattr(args, "lint_fix", False)
        exit_on_error = not getattr(args, "lint_no_exit", False)
        run_ruff_lint(directories=[lint_dir], fix=lint_fix, exit_on_error=exit_on_error)
    else:
        print("[prepare] Lint step disabled. Skipping linting.")

    # --------------------------------------------------
    # 3. Format code
    # --------------------------------------------------
    if not getattr(args, "disable_format", False):
        format_dir = args.directory or "."
        # Run Ruff's format command; here we always continue on formatting errors.
        run_ruff_format(directories=[format_dir], exit_on_error=False)
    else:
        print("[prepare] Format step disabled. Skipping formatting.")

    # --------------------------------------------------
    # 4. Git commit changes
    # --------------------------------------------------
    commit_msg = getattr(args, "commit_msg", "chore: prepare changes")
    success = git_commit_all_changes(commit_msg)
    if not success:
        print("[prepare] Git commit failed or there were no changes to commit.")
        # Optionally, you might want to exit or handle this failure further.

    print("[prepare] Complete.")
