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
      - Validate (test-only, but in "each" mode we get subpackage results)
      - For aggregator + each-mode, build/update/publish only subpackages that passed
      - For monorepo or single-mode, either all pass => build/publish, or fail => exit
      - Remote update (optionally aggregator or subpackages)
    """

    print("[release] Running validation (test only).")
    test_results = run_validate(args)
    test_mode = getattr(args, "test_mode", "single")

    if test_mode != "each":
        # monorepo or single => if success, build + remote update + publish all; else fail
        if not test_results["success"]:
            print("[release] Some tests failed in monorepo/single mode. Exiting.", file=sys.stderr)
            sys.exit(1)

        print("[release] Tests passed. Building all packages ...")
        build_ok = build_packages(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive
        )
        if not build_ok:
            print("[release] Build failed. Exiting.", file=sys.stderr)
            sys.exit(1)

        print("[release] Remote update ...")
        if not remote_update_bulk(
            file=args.file,
            directory=args.directory,
            recursive=args.recursive
        ):
            print("[release] Remote update failed. Exiting.", file=sys.stderr)
            sys.exit(1)

        print("[release] Publishing packages ...")
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

        print("[release] Done.")
        return

    # ------------------------------------------------------------------
    # If test_mode == "each", partial pass scenario:
    # we check aggregator or multiple pyprojects, build/publish only those that pass
    # ------------------------------------------------------------------
    if not test_results["details"]:
        print("[release] No subpackages tested? Exiting.", file=sys.stderr)
        sys.exit(1)

    # We assume the first pyproject is the aggregator if aggregator is True
    pyprojects = find_pyproject_files(args.file, args.directory, args.recursive)
    if not pyprojects:
        print("[release] No pyprojects found, can't proceed.", file=sys.stderr)
        sys.exit(1)

    aggregator_pyproj = pyprojects[0]
    is_agg, agg_name = _check_if_aggregator(aggregator_pyproj)

    # Collect a list of subpackage directories that passed
    passed_dirs = [
        d["directory"] for d in test_results["details"] if d["success"]
    ]
    if not passed_dirs:
        print("[release] All subpackages failed. Nothing to publish.", file=sys.stderr)
        sys.exit(1)

    # Possibly do aggregator-level remote update once if aggregator
    if is_agg:
        print(f"[release] Aggregator '{agg_name}' detected. Doing aggregator-level remote update once ...")
        ru_ok = remote_update_bulk(
            file=aggregator_pyproj,
            directory=None,  # or aggregator's directory
            recursive=False
        )
        if not ru_ok:
            print("[release] Remote update failed. Exiting.", file=sys.stderr)
            sys.exit(1)
    else:
        # If not aggregator, optional. If you have multiple packages each with its own pyproject,
        # you might do remote update on each. We'll do a single recursion for all.
        print("[release] Non-aggregator. Doing a single remote update for all found pyprojects ...")
        ru_ok = remote_update_bulk(
            file=None,
            directory=args.directory,
            recursive=args.recursive
        )
        if not ru_ok:
            print("[release] Remote update failed. Exiting.", file=sys.stderr)
            sys.exit(1)

    # Now for each subpackage that passed, do a build & publish
    # We'll skip aggregator itself, if aggregator is not meant to be published
    overall_publish_success = True
    for sub_dir in passed_dirs:
        # If aggregator is the same dir, skip
        if is_agg and (os.path.abspath(sub_dir) == os.path.dirname(aggregator_pyproj)):
            print(f"[release] Skipping aggregator dir {sub_dir}.")
            continue

        print(f"\n[release] Building subpackage: {sub_dir}")
        build_rc = run_command(["poetry", "build"], cwd=sub_dir)
        if build_rc != 0:
            print(f"[release] Build failed in {sub_dir}", file=sys.stderr)
            overall_publish_success = False
            continue

        print(f"[release] Publishing subpackage: {sub_dir}")
        publish_cmd = ["poetry", "publish", '-vv']
        uname = "__token__"
        pwd = getattr(args, "publish_password", None)
        publish_cmd.extend(["--username", uname])
        if pwd:
            publish_cmd.extend(["--password", pwd])

        pub_rc = run_command(publish_cmd, cwd=sub_dir)
        if pub_rc != 0:
            print(f"[release] Publish failed in {sub_dir}", file=sys.stderr)
            overall_publish_success = False

    if not overall_publish_success:
        print("[release] Some subpackages failed to build or publish.", file=sys.stderr)
        sys.exit(1)

    print("\n[release] Done. All passing subpackages have been published.")
