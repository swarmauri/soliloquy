# myworkflow/cli.py

import argparse
import sys

# Import our phases
from soliloquy.phases.prepare import run_prepare
from soliloquy.phases.validate import run_validate
from soliloquy.phases.release import run_release

def main():
    parser = argparse.ArgumentParser(
        prog="soliloquy",
        description="A CLI for preparing, validating, and releasing Python packages."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # -------------------------------------------------------------------------
    # prepare
    # -------------------------------------------------------------------------
    prepare_parser = subparsers.add_parser("prepare", help="Bump/set version, lint, and commit changes.")
    # Version ops
    prepare_parser.add_argument("-f", "--file", help="Path to a single pyproject.toml.")
    prepare_parser.add_argument("-d", "--directory", help="Directory containing one or more pyproject.toml.")
    prepare_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    prepare_parser.add_argument("--bump", choices=["major","minor","patch","finalize"], help="Bump version type.")
    prepare_parser.add_argument("--set-ver", help="Explicit version to set, e.g. '2.0.0.dev1'.")
    # Lint + commit
    prepare_parser.add_argument("--commit-msg", default="chore: prepare changes", help="Git commit message.")

    # -------------------------------------------------------------------------
    # validate
    # -------------------------------------------------------------------------
    validate_parser = subparsers.add_parser("validate", help="Build, install, test, analyze.")
    validate_parser.add_argument("-f", "--file", help="Path to a single pyproject.toml.")
    validate_parser.add_argument("-d", "--directory", help="Directory with multiple pyprojects or aggregator.")
    validate_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    validate_parser.add_argument("--test-mode", choices=["single","monorepo","each"], default="single",
                                 help="How to run tests: single run, one big monorepo run, or each subpackage.")
    validate_parser.add_argument("--num-workers", type=int, default=1, help="Number of parallel pytest workers.")
    # Analysis
    validate_parser.add_argument("--results-json", help="Path to a JSON test-results file for analysis.")
    validate_parser.add_argument("--required-passed", help="e.g. 'ge:80' => require at least 80 percent passed.")
    validate_parser.add_argument("--required-skipped", help="e.g. 'lt:10' => require fewer than 10 percent skipped.")

    # -------------------------------------------------------------------------
    # release
    # -------------------------------------------------------------------------
    release_parser = subparsers.add_parser("release", help="Validate + remote update + publish.")
    release_parser.add_argument("-f", "--file", help="Path to a single pyproject.toml.")
    release_parser.add_argument("-d", "--directory", help="Directory with multiple pyprojects or aggregator.")
    release_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    release_parser.add_argument("--test-mode", choices=["single","monorepo","each"], default="single",
                                help="How to run tests.")
    release_parser.add_argument("--num-workers", type=int, default=1, help="Number of parallel pytest workers.")
    release_parser.add_argument("--results-json", help="JSON results file for analysis.")
    release_parser.add_argument("--required-passed", help="e.g. 'ge:80'.")
    release_parser.add_argument("--required-skipped", help="e.g. 'lt:10'.")

    # Publish credentials
    release_parser.add_argument("--publish-username", help="PyPI username.")
    release_parser.add_argument("--publish-password", help="PyPI password.")
    release_parser.add_argument("--repository", help="Custom Poetry repository name (optional).")

    # Parse arguments
    args = parser.parse_args()

    # Dispatch to the correct phase function
    if args.command == "prepare":
        run_prepare(args)
    elif args.command == "validate":
        run_validate(args)
    elif args.command == "release":
        run_release(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
