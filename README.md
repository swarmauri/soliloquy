<p align="center">
    <a href="https://github.com/swarmauri/swarmauri-sdk/"><img src="https://res.cloudinary.com/dbjmpekvl/image/upload/v1730099724/Swarmauri-logo-lockup-2048x757_hww01w.png" alt="Swamauri Logo"/></a>
    <br />
    <a href="https://hits.sh/github.com/swarmauri/soliloquy/"><img src="https://hits.sh/github.com/swarmauri/soliloquy.svg" alt="Hits"/></a>
    <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"/></a>
    <a href="https://pypi.org/project/soliloquy/"><img src="https://img.shields.io/pypi/v/soliloquy?label=soliloquy" alt="PyPI - soliloquy Version"/></a>
    <a href="https://pypi.org/project/soliloquy/"><img src="https://img.shields.io/pypi/dm/soliloquy?label=soliloquy%20Downloads" alt="PyPI - soliloquy Downloads"/></a>
    <br />
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&labelColor=black" alt="Python"/>
</p>


Below is a complete example of a `README.md` for your Soliloquy project:

---

<p align="center">
  <a href="https://github.com/swarmauri/swarmauri-sdk/">
    <img src="https://res.cloudinary.com/dbjmpekvl/image/upload/v1730099724/Swarmauri-logo-lockup-2048x757_hww01w.png" alt="Swamauri Logo"/>
  </a>
  <br />
  <a href="https://hits.sh/github.com/swarmauri/soliloquy/">
    <img src="https://hits.sh/github.com/swarmauri/soliloquy.svg" alt="Hits"/>
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"/>
  </a>
  <a href="https://pypi.org/project/soliloquy/">
    <img src="https://img.shields.io/pypi/v/soliloquy?label=soliloquy" alt="PyPI - soliloquy Version"/>
  </a>
  <a href="https://pypi.org/project/soliloquy/">
    <img src="https://img.shields.io/pypi/dm/soliloquy?label=soliloquy%20Downloads" alt="PyPI - soliloquy Downloads"/>
  </a>
  <br />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&labelColor=black" alt="Python"/>
</p>

# Soliloquy

**Soliloquy** is a unified command-line tool for managing a Python monorepo that contains multiple standalone packages—each with its own `pyproject.toml`. It consolidates common tasks such as dependency management, version bumping, remote dependency resolution, test execution and analysis, and project configuration updates into one robust CLI.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Commands](#commands)
    - [Prepare](#prepare)
    - [Install](#install)
    - [Validate](#validate)
    - [Release](#release)
- [Configuration](#configuration)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **Version Management:** Automatically bump or set versions (major, minor, patch, or finalize) across projects.
- **Dependency Management:** Lock and install dependencies from single or multiple `pyproject.toml` files.
- **Validation:** Build, test, and analyze code with configurable test modes and parallel execution support.
- **Release Workflow:** Validate, update remote dependencies, and publish to PyPI with a single command.
- **Recursive Discovery:** Automatically scan directories (and subdirectories) to find `pyproject.toml` files.

## Installation

Install Soliloquy directly from PyPI:

```bash
pip install soliloquy
```

Alternatively, install from source:

```bash
git clone https://github.com/swarmauri/soliloquy.git
cd soliloquy
pip install .
```

## Usage

After installation, you can run Soliloquy from the command line:

```bash
soliloquy --help
```

This command displays the available commands and options.

### Commands

Soliloquy includes several commands for different stages of your workflow:

#### Prepare

Bump or set version numbers, lint your code, and commit changes.

**Options:**

- `-f`, `--file`: Specify a single `pyproject.toml` file.
- `-d`, `--directory`: Specify a directory containing one or more `pyproject.toml` files.
- `-R`, `--recursive`: Recursively find `pyproject.toml` files.
- `--bump`: Select the type of version bump (`major`, `minor`, `patch`, or `finalize`).
- `--set-ver`: Explicitly set a version (e.g., `2.0.0.dev1`).
- `--commit-msg`: Set the Git commit message (default: `"chore: prepare changes"`).

**Example:**

```bash
soliloquy prepare --bump patch -d ./packages
```

#### Install

Lock dependencies and install packages across your projects.

**Options:**

- `-f`, `--file`: Specify a single `pyproject.toml` file.
- `-d`, `--directory`: Specify a directory with multiple projects or an aggregator.
- `-R`, `--recursive`: Recursively find `pyproject.toml` files.

**Example:**

```bash
soliloquy install -d ./projects --recursive
```

#### Validate

Build, test, and analyze your code.

**Options:**

- `-f`, `--file`: Specify a single `pyproject.toml` file.
- `-d`, `--directory`: Specify a directory with multiple projects.
- `-R`, `--recursive`: Recursively find `pyproject.toml` files.
- `--test-mode`: Choose the test mode (`single`, `monorepo`, or `each`; default: `single`).
- `--num-workers`: Number of parallel pytest workers (default: `1`).
- `--results-json`: Path to a JSON file with test results for analysis.
- `--required-passed`: Set a requirement for passed tests (e.g., `ge:80`).
- `--required-skipped`: Set a requirement for skipped tests (e.g., `lt:10`).
- `--no-cleanup`: Prevent cleanup of temporary test directories for Git-based dependencies.

**Example:**

```bash
soliloquy validate -d ./src --test-mode monorepo --num-workers 4
```

#### Release

Validate, update remote dependencies, and publish your package to PyPI.

**Options:**

- `-f`, `--file`: Specify a single `pyproject.toml` file.
- `-d`, `--directory`: Specify a directory with multiple projects.
- `-R`, `--recursive`: Recursively find `pyproject.toml` files.
- `--test-mode`: Choose the test mode (default: `single`).
- `--num-workers`: Number of parallel pytest workers (default: `1`).
- `--results-json`: Path to a JSON file with test results.
- `--required-passed`: Set a requirement for passed tests.
- `--required-skipped`: Set a requirement for skipped tests.
- `--publish-password`: Provide your PyPI password for publishing.
- `--no-cleanup`: Prevent cleanup of temporary test directories.

**Example:**

```bash
soliloquy release -d ./myproject --publish-password YOUR_PYPI_PASSWORD
```

## Configuration

Soliloquy leverages the configuration defined in your `pyproject.toml` files. To get the most out of Soliloquy, ensure that each project within your monorepo is correctly configured. For more details on configuration options and best practices, please refer to the [official documentation](https://github.com/swarmauri/soliloquy).

## Examples

Here are some practical use cases:

- **Prepare a release by bumping the patch version:**

  ```bash
  soliloquy prepare --bump patch -d ./packages
  ```

- **Install dependencies across all projects recursively:**

  ```bash
  soliloquy install -d ./monorepo --recursive
  ```

- **Run tests in monorepo mode with multiple workers:**

  ```bash
  soliloquy validate -d ./src --test-mode monorepo --num-workers 4
  ```

- **Release your package after validation:**

  ```bash
  soliloquy release -d ./myproject --publish-password YOUR_PYPI_PASSWORD
  ```

## Contributing

Contributions are welcome! If you’d like to contribute:

1. **Fork the Repository:** Create your own fork on GitHub.
2. **Create a Branch:** Work on a new feature or bugfix.
3. **Write Tests:** Ensure your changes are covered by tests.
4. **Submit a Pull Request:** Provide a detailed description of your changes.

Please review our [CONTRIBUTING.md](CONTRIBUTING.md) for more details on our contribution process.

## License

This project is licensed under the [Apache 2.0 License](https://opensource.org/licenses/Apache-2.0).

## Contact

For questions, suggestions, or further information, please open an issue on [GitHub](https://github.com/swarmauri/soliloquy) or reach out directly.

---

Happy coding with Soliloquy! 🚀