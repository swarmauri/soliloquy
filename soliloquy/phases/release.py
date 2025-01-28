# soliloquy/phases/release.py

import sys
from typing import Any

from soliloquy.phases.validate import run_validate
from soliloquy.ops.build_ops import build_packages
from soliloquy.ops.remote_ops import remote_update_bulk
from soliloquy.ops.publish_ops import publish_packages


def run_release(args: Any) -> None:
    """
    The 'release' phase:
      1. Validate (build, install, test, analyze)
      2. 
      3. Remote update any Git-based dependencies
      4. Publish

    If any step fails, we exit.
    """

    # (1) Validate
    print("[release] Running validation (includes 'poetry lock')...")
    try:
        run_validate(args)  # This may sys.exit(1) on failure
    except SystemExit as e:
        print("[release] Validation failed. Exiting release step.", file=sys.stderr)
        sys.exit(e.code)

    # (2) Build
    print("[validate] Building packages...")
    build_ok = build_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not build_ok:
        print("[validate] Build failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    # (3) Remote update
    print("[release] Updating remote Git-based dependencies...")
    success = remote_update_bulk(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        output=None
    )
    if not success:
        print("[release] Remote update failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    # (4) Publish
    print("[release] Publishing packages to PyPI (or custom repo)...")
    repository = getattr(args, "repository", None)
    pub_ok = publish_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        username=getattr(args, "publish_username", None),
        password=getattr(args, "publish_password", None),
        repository=repository
    )
    if not pub_ok:
        print("[release] Publish failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("[release] Completed successfully.")
