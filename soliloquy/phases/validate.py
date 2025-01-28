# soliloquy/phases/validate.py

import sys
from typing import Any, Dict

from soliloquy.ops.test_ops import run_tests_with_mode
from soliloquy.ops.analyze_ops import analyze_test_file


def run_validate(args: Any) -> Dict:
    """
    The 'validate' phase:
      1. Test
      2. Analyze (optional if --results-json is provided)

    Returns a dictionary with detailed test results:
      {
        "success": bool,  # True if all subpackages passed, else False
        "details": [
          {
            "success": bool,
            "returncode": int,
            "directory": str,
          },
          ...
        ]
      }

    The caller (e.g. release) can then decide what to do per-package.
    """
    print("[validate] Running tests...")

    # 1) Test
    test_results = run_tests_with_mode(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        mode=args.test_mode,
        num_workers=args.num_workers
    )

    # 2) Analyze if we have --results-json
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
        # If analysis fails, we consider overall success = False
        if not analysis_ok:
            test_results["success"] = False
            print("[validate] Analysis indicates thresholds not met.")

    print("[validate] Completed with success =", test_results["success"])
    return test_results