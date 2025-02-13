# soliloquy/phases/release.py

import sys
import os
from typing import Any

from soliloquy.phases.validate import run_validate
from soliloquy.ops.poetry_utils import run_command
from soliloquy.ops.pyproject_ops import find_pyproject_files
from soliloquy.ops.remote_ops import remote_update_bulk
from soliloquy.ops.publish_ops import publish_packages
from soliloquy.ops.test_ops import _check_if_aggregator  # or re-implement aggregator check
from soliloquy.ops.build_ops import build_packages


def run_release(args: Any) -> None:
    """
    The 'release' phase:
      - Validate (test-only, in user-specified mode)
      - Perform remote_update_bulk (to update references in pyproject.toml).
      - Build + publish, in different ways depending on mode.

    Changes to fix the remote_update_bulk call in single/monorepo mode:
      - If mode != 'each', also call remote_update_bulk on the local file/directory 
        (not just the aggregator in a Git clone).
    """

    print("[release] Running validation (test only).")
    test_results = run_validate(args)
    test_mode = getattr(args, "test_mode", "single")

    # Overall test success or failure
    overall_success = test_results.get("success", False)
    # Each-mode test detail array
    details = test_results.get("details", [])
    # The temp directory containing cloned Git deps (only relevant if aggregator + each-mode + Git deps)
    git_temp_dir = test_results.get("git_temp_dir")

    # ------------------------------------------------------------------
    # SINGLE / MONOREPO MODE
    # ------------------------------------------------------------------
    if test_mode != "each":
        if not overall_success:
            print(f"[release] Tests failed in '{test_mode}' mode. Exiting.", file=sys.stderr)
            sys.exit(1)

        # ====== NEW: Perform remote update on local file/directory ======
        print("[release] Tests passed. Performing remote update on local pyproject(s)...")
        ru_result = remote_update_bulk(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive,
            output=None  # In-place update
        )

        if not ru_result["overall_success"]:
            print("[release] Some remote updates failed, continuing with build/publish.")
            for file_result in ru_result["results"]:
                if not file_result["success"]:
                    print(f"    - Update failed for {file_result['file']}: {file_result['error']}", file=sys.stderr)
        else:
            print("[release] All remote updates succeeded in local pyproject(s).")

        # Build
        print("[release] Building packages ...")
        build_ok = build_packages(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive
        )
        if not build_ok:
            print("[release] Build failed. Exiting.", file=sys.stderr)
            sys.exit(1)

        # Publish
        print("[release] Publishing packages ...")
        repository = getattr(args, "repository", None)
        pub_ok = publish_packages(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive,
            username="__token__",
            password=getattr(args, "publish_password", None),
            repository=repository
        )
        if not pub_ok:
            print("[release] Publish failed. Exiting.", file=sys.stderr)
            sys.exit(1)

        print("[release] Done.")
        return

    # ------------------------------------------------------------------
    # EACH MODE
    # ------------------------------------------------------------------
    if not details:
        print("[release] No test details found in 'each' mode. Exiting.", file=sys.stderr)
        sys.exit(1)

    passed_dirs = [d["directory"] for d in details if d["success"]]
    if not passed_dirs:
        print("[release] All subpackages failed in 'each' mode. Nothing to publish.", file=sys.stderr)
        sys.exit(1)

    # We assume the first pyproject might be an aggregator if aggregator=True,
    # but we are *not* going to do a direct remote update on aggregator or local subdirs
    # in the main repo. We only update the cloned subprojects in git_temp_dir.
    pyprojects = find_pyproject_files(args.file, args.directory, args.recursive)
    aggregator_pyproj = pyprojects[0] if pyprojects else None
    is_agg, agg_name = _check_if_aggregator(aggregator_pyproj) if aggregator_pyproj else (False, "N/A")

    # 1) Remote update is performed **only** on the temporary clone folder, if it exists.
    #    Partial failures do not block the rest of the release. We simply log them.
    if git_temp_dir:
        print(f"[release] Performing remote update on cloned Git dependencies at: {git_temp_dir}")
        ru_result = remote_update_bulk(
            file=None,
            directory=git_temp_dir,
            recursive=True,
            output=None  # In-place in the temp folder
        )
        if not ru_result["overall_success"]:
            print("[release] Some remote updates failed, but continuing with build/publish.")
            for file_result in ru_result["results"]:
                if not file_result["success"]:
                    print(f"    - Update failed for {file_result['file']}: {file_result['error']}",
                          file=sys.stderr)
        else:
            print("[release] All remote updates succeeded in the temporary directory.")
    else:
        print("[release] No temporary Git clone directory found. Skipping remote update of aggregator or local repos.")

    # 2) Build & Publish only the subpackages that passed tests. 
    #    (Likely subpackages in the cloned git_temp_dir).
    overall_publish_success = True
    for sub_dir in passed_dirs:
        # If aggregator, skip building/publishing aggregator
        if is_agg and os.path.abspath(sub_dir) == os.path.dirname(aggregator_pyproj):
            print(f"[release] Skipping aggregator dir {sub_dir} for build/publish.")
            continue

        # Build
        print(f"\n[release] Building subpackage: {sub_dir}")
        build_rc, out_build, err_build = run_command(["poetry", "build"], cwd=sub_dir)
        if build_rc != 0:
            print(f"[release] Build failed in {sub_dir}", file=sys.stderr)
            if out_build:
                print(f"STDOUT: {out_build}")
            if err_build:
                print(f"STDERR: {err_build}", file=sys.stderr)
            overall_publish_success = False
            continue

        # Publish
        print(f"[release] Publishing subpackage: {sub_dir}")
        publish_cmd = ["poetry", "publish", "-vv"]
        uname = "__token__"  # Typically used if passing a token
        pwd = getattr(args, "publish_password", None)

        publish_cmd.extend(["--username", uname])
        if pwd:
            publish_cmd.extend(["--password", pwd])

        pub_rc, out_pub, err_pub = run_command(publish_cmd, cwd=sub_dir)
        if pub_rc != 0:
            print(f"[release] Publish failed in {sub_dir}", file=sys.stderr)
            if out_pub:
                print(f"STDOUT: {out_pub}")
            if err_pub:
                print(f"STDERR: {err_pub}", file=sys.stderr)
            overall_publish_success = False

    if not overall_publish_success:
        print("[release] Some subpackages failed to build or publish.", file=sys.stderr)
        sys.exit(1)

    print("\n[release] Done. All passing subpackages have been published from the temporary folder.")
