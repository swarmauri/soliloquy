# soliloquy/cli.py

import argparse
import sys

# Import the phases
from soliloquy.phases.prepare import run_prepare
from soliloquy.phases.install import run_install
from soliloquy.phases.validate import run_validate
from soliloquy.phases.release import run_release

def main():
    parser = argparse.ArgumentParser(
        prog="soliloquy",
        description="A CLI for preparing, installing, validating, and releasing Python packages."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # -------------------------------------------------------------------------
    # prepare
    # -------------------------------------------------------------------------
    prepare_parser = subparsers.add_parser("prepare", help="Bump/set version, lint, commit.")
    prepare_parser.add_argument("-f", "--file", help="Path to a single pyproject.toml.")
    prepare_parser.add_argument("-d", "--directory", help="Directory containing pyprojects or aggregator.")
    prepare_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    prepare_parser.add_argument("--bump", choices=["major","minor","patch","finalize"], help="Type of version bump.")
    prepare_parser.add_argument("--set-ver", help="Explicit version to set, e.g. '2.0.0.dev1'.")
    prepare_parser.add_argument("--commit-msg", default="chore: prepare changes", help="Git commit message.")

    # -------------------------------------------------------------------------
    # install
    # -------------------------------------------------------------------------
    install_parser = subparsers.add_parser("install", help="Lock then install packages.")
    install_parser.add_argument("-f", "--file", help="Single pyproject.toml.")
    install_parser.add_argument("-d", "--directory", help="Directory with multiple pyprojects or aggregator.")
    install_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")

    # -------------------------------------------------------------------------
    # validate
    # -------------------------------------------------------------------------
    validate_parser = subparsers.add_parser("validate", help="Build, test, analyze.")
    validate_parser.add_argument("-f", "--file", help="Path to a single pyproject.toml.")
    validate_parser.add_argument("-d", "--directory", help="Directory with multiple pyprojects or aggregator.")
    validate_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    validate_parser.add_argument("--test-mode", choices=["single","monorepo","each"], default="single",
                                 help="How to run tests.")
    validate_parser.add_argument("--num-workers", type=int, default=1, help="Parallel pytest workers.")
    validate_parser.add_argument("--results-json", help="Path to a JSON test-results file for analysis.")
    validate_parser.add_argument("--required-passed", help="e.g. 'ge:80'.")
    validate_parser.add_argument("--required-skipped", help="e.g. 'lt:10'.")

    # -------------------------------------------------------------------------
    # release
    # -------------------------------------------------------------------------
    release_parser = subparsers.add_parser("release", help="Validate, remote update, publish.")
    release_parser.add_argument("-f", "--file", help="Single pyproject.toml.")
    release_parser.add_argument("-d", "--directory", help="Directory with multiple pyprojects or aggregator.")
    release_parser.add_argument("-R", "--recursive", action="store_true", help="Recursively find pyproject.toml files.")
    release_parser.add_argument("--test-mode", choices=["single","monorepo","each"], default="single")
    release_parser.add_argument("--num-workers", type=int, default=1)
    release_parser.add_argument("--results-json", help="JSON test-results file for analysis.")
    release_parser.add_argument("--required-passed", help="e.g. 'ge:80'.")
    release_parser.add_argument("--required-skipped", help="e.g. 'lt:10'.")
    release_parser.add_argument("--publish-username", help="PyPI username.")
    release_parser.add_argument("--publish-password", help="PyPI password.")
    release_parser.add_argument("--repository", help="Custom Poetry repository name.")

    # Parse arguments
    args = parser.parse_args()

    # Dispatch
    if args.command == "prepare":
        run_prepare(args)
    elif args.command == "install":
        run_install(args)
    elif args.command == "validate":
        run_validate(args)
    elif args.command == "release":
        run_release(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
