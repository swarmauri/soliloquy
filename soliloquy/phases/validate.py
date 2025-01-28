# soliloquy/phases/validate.py

import sys
from typing import Any, Dict

from soliloquy.ops.test_ops import run_tests_with_mode
from soliloquy.ops.analyze_ops import analyze_test_file
from soliloquy.ops.build_ops import build_packages  # If you still have a build step here

def run_validate(args: Any) -> Dict:
    """
    The 'validate' phase:
      1. Build (if you still have it)
      2. Test
      3. Analyze

    Returns test results dictionary:
      {
        "success": bool,
        "details": [...]
      }
    """

    # Possibly build step first (if your design includes build in validate):
    print("[validate] Building packages...")
    build_ok = build_packages(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive
    )
    if not build_ok:
        print("[validate] Build failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    # 2) Test
    # NOTE: read the no_cleanup flag
    cleanup_bool = not getattr(args, "no_cleanup", False)

    print("[validate] Running tests (cleanup=%s)..." % cleanup_bool)
    test_results = run_tests_with_mode(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        mode=getattr(args, "test_mode", "single"),
        num_workers=getattr(args, "num_workers", 1),
        cleanup=cleanup_bool
    )

    # 3) Analyze if you have results JSON
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
            test_results["success"] = False
            print("[validate] Analysis thresholds not met. Exiting with code 1.")
            sys.exit(1)

    if not test_results["success"]:
        print("[validate] Some tests failed. Exiting with code 1.")
        sys.exit(1)

    print("[validate] Completed successfully.")
    return test_results
