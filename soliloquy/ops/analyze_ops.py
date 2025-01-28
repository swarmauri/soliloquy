# myworkflow/ops/analyze_ops.py

import json
import sys
from collections import defaultdict
from typing import Optional, Dict


def evaluate_threshold(value: float, threshold: str) -> bool:
    """
    Evaluate if 'value' meets the specified threshold condition (e.g., "gt:50").

    The threshold format: "<operator>:<limit>", where <operator> ∈ {gt, lt, eq, ge, le}.
    Example: "gt:50" means value > 50.
    """
    try:
        op, limit_str = threshold.split(":")
        limit = float(limit_str)
    except ValueError as e:
        raise ValueError(f"Invalid threshold format '{threshold}'. Expected 'gt:NN' or 'lt:NN', etc.") from e

    if op == "gt":
        return value > limit
    elif op == "lt":
        return value < limit
    elif op == "eq":
        return value == limit
    elif op == "ge":
        return value >= limit
    elif op == "le":
        return value <= limit
    else:
        raise ValueError(f"Invalid operator '{op}'. Use 'gt', 'lt', 'eq', 'ge', or 'le'.")


def analyze_test_file(
    file_path: str,
    required_passed: Optional[str] = None,
    required_skipped: Optional[str] = None
) -> bool:
    """
    Analyzes a JSON test results file with the structure:
      {
        "summary": {"total": <int>, "passed": <int>, "failed": <int>, "skipped": <int>},
        "tests": [
          {
            "outcome": "passed|failed|skipped",
            "keywords": ["some_tag", ...]
          },
          ...
        ]
      }

    Steps:
      1. Reads and parses the JSON from 'file_path'.
      2. Prints a summary table of test outcomes.
      3. If 'required_passed' or 'required_skipped' thresholds are given (e.g., "ge:80"),
         it checks whether the percentages of passed/skipped meet those thresholds.
      4. Groups tests by "keywords"/tags and prints a per-tag breakdown.

    Returns:
      True if all thresholds are met and no parsing error occurs; False otherwise.
    """

    # Load the JSON file
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[analyze_ops] File not found: {file_path}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"[analyze_ops] JSON decode error in {file_path}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[analyze_ops] Unexpected error reading {file_path}: {e}", file=sys.stderr)
        return False

    summary = data.get("summary", {})
    tests = data.get("tests", [])
    if not summary or not tests:
        print("[analyze_ops] Invalid or empty test results (no 'summary' or 'tests')", file=sys.stderr)
        return False

    total_tests = summary.get("total", 0)
    passed_count = summary.get("passed", 0)
    failed_count = summary.get("failed", 0)
    skipped_count = summary.get("skipped", 0)

    if total_tests == 0:
        print("[analyze_ops] No tests found (total=0).", file=sys.stderr)
        return False

    # Print summary table
    print("\nTest Results Summary:")
    print(f"{'Category':<15}{'Count':<10}{'Total':<10}{'% of Total':<10}")
    print("-" * 50)

    for cat in ["passed", "skipped", "failed"]:
        cat_count = summary.get(cat, 0)
        pct = (cat_count / total_tests * 100.0) if total_tests else 0
        print(f"{cat.capitalize():<15}{cat_count:<10}{total_tests:<10}{pct:<10.2f}")

    # Evaluate thresholds if provided
    passed_pct = (passed_count / total_tests * 100.0)
    skipped_pct = (skipped_count / total_tests * 100.0)
    threshold_fail = False

    if required_passed:
        if not evaluate_threshold(passed_pct, required_passed):
            print(f"[analyze_ops] Passed tests did not meet threshold {required_passed} (actual={passed_pct:.2f}%)",
                  file=sys.stderr)
            threshold_fail = True

    if required_skipped:
        if not evaluate_threshold(skipped_pct, required_skipped):
            print(f"[analyze_ops] Skipped tests did not meet threshold {required_skipped} (actual={skipped_pct:.2f}%)",
                  file=sys.stderr)
            threshold_fail = True

    # Group tests by tags (keywords)
    tag_stats = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "skipped": 0})
    for test in tests:
        outcome = test.get("outcome", "").lower()
        for tag in test.get("keywords", []):
            # Exclude empty or trivial tags if you want
            if not tag or tag.strip() == "" or tag == "tests":
                continue

            stats = tag_stats[tag]
            stats["total"] += 1
            if outcome == "passed":
                stats["passed"] += 1
            elif outcome == "failed":
                stats["failed"] += 1
            elif outcome == "skipped":
                stats["skipped"] += 1

    if tag_stats:
        print("\nTag-Based Results:")
        header = f"{'Tag':<30}{'Passed':<10}{'Skipped':<10}{'Failed':<10}{'Total':<10}{'% Passed':<10}{'% Skipped':<10}{'% Failed':<10}"
        print(header)
        print("-" * len(header))

        # Sort tags by descending pass rate
        sorted_tags = sorted(tag_stats.items(), key=lambda kv: -(kv[1]["passed"] / kv[1]["total"] if kv[1]["total"] else 0))
        for tag, st in sorted_tags:
            t = st["total"]
            pass_pct = (st["passed"] / t * 100.0) if t else 0
            skip_pct = (st["skipped"] / t * 100.0) if t else 0
            fail_pct = (st["failed"] / t * 100.0) if t else 0
            print(f"{tag:<30}{st['passed']:<10}{st['skipped']:<10}{st['failed']:<10}"
                  f"{t:<10}{pass_pct:<10.2f}{skip_pct:<10.2f}{fail_pct:<10.2f}")

    if threshold_fail:
        print("[analyze_ops] Threshold conditions not met. Analysis failed.", file=sys.stderr)
        return False

    if failed_count > 0:
        print("[analyze_ops] Some tests failed. If that's unacceptable, handle accordingly.", file=sys.stderr)
        # Depending on your policy, you might return False
        # For now, let's just not forcibly fail if thresholds for pass/skip are not set.
        # return False

    print("[analyze_ops] Analysis completed successfully.")
    return True
