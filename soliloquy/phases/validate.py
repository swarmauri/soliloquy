# soliloquy/phases/validate.py

import sys
from typing import Any, Dict, Union, List, Optional

from soliloquy.ops.test_ops import run_tests_with_mode
from soliloquy.ops.analyze_ops import analyze_test_file
from soliloquy.ops.build_ops import build_packages  # If you still have a build step here


def run_validate(args: Any) -> Dict[str, Union[bool, List[Dict[str, Union[bool, int, str]]], Optional[str]]]:
    """
    The 'validate' phase:
      1. Test
      2. Analyze

    Returns test results dictionary:
      {
        "success": bool,
        "details": List[Dict],
        "git_temp_dir": Optional[str],
      }
    """

    # 1) Test
    # Read the 'no_cleanup' flag to determine whether to clean up temporary directories
    cleanup_bool = not getattr(args, "no_cleanup", False)

    print(f"[validate] Running tests (cleanup={'enabled' if cleanup_bool else 'disabled'})...")
    test_results = run_tests_with_mode(
        file=args.file,
        directory=args.directory,
        recursive=args.recursive,
        mode=getattr(args, "test_mode", "single"),
        num_workers=getattr(args, "num_workers", 1),
        cleanup=cleanup_bool
    )

    # 2) Analyze if '--results-json' is provided
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
        # If analysis fails, set overall success to False
        if not analysis_ok:
            test_results["success"] = False
            print("[validate] Analysis indicates thresholds not met.")

    print(f"[validate] Completed with success = {test_results['success']}")
    return test_results
