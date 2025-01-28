# soliloquy/phases/validate.py

import sys
from typing import Any

from soliloquy.ops.lock_ops import lock_packages
from soliloquy.ops.build_ops import build_packages
from soliloquy.ops.install_ops import install_packages
from soliloquy.ops.test_ops import run_tests_with_mode
from soliloquy.ops.analyze_ops import analyze_test_file


def run_validate(args: Any) -> None:
    """
    The 'validate' phase now includes:
      1. Lock
      2. Build
      3. Install
      4. Test
      5. Analyze
    """
    # (1) Lock
    print("[validate] Locking packages...")
    lock_ok = lock_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not lock_ok:
        print("[validate] 'poetry lock' failed. Exiting.", file=sys.stderr)
        sys.exit(1)

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

    # (3) Install
    print("[validate] Installing packages...")
    install_ok = install_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not install_ok:
        print("[validate] Install failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    # (4) Test
    print("[validate] Running tests...")
    test_results = run_tests_with_mode(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        mode=args.test_mode,
        num_workers=args.num_workers
    )
    if not test_results["success"]:
        print("[validate] Some tests failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    # (5) Analyze
    results_json_file = getattr(args, "results_json", None)
    if results_json_file:
        print(f"[validate] Analyzing test results from {results_json_file} ...")
        required_passed = getattr(args, "required_passed", None)
        required_skipped = getattr(args, "required_skipped", None)
        analysis_ok = analyze_test_file(
            file_path=results_json_file,
            required_passed=required_passed,
            required_skipped=required_skipped
        )
        if not analysis_ok:
            print("[validate] Analysis failed. Exiting.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[validate] No test results JSON provided; skipping analysis step.")

    print("[validate] Completed successfully.")
