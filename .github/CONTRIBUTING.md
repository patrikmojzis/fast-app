# Contributing Guide

Thanks for your interest in FastApp! This framework thrives on lean, elegant contributions. Please follow the steps below to keep the project consistent and high quality.

## Getting Started
- Use Python 3.12.
- Create a virtual environment and install dependencies:
- Use one-line activation when installing dependencies per project conventions:

```sh
python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]
```
- Run the full test suite to confirm a clean baseline:

```sh
pytest
```

## Development Workflow
- Keep pull requests focused and small; one logical change per PR.
- Follow existing coding style; format with `black` and `isort` before submitting.
- Run `pytest`
- Prefer composition over duplication; remove redundancy where possible.
- Keep public APIs stable unless coordinated with maintainers.

## Testing
- Tests are required for new features and bug fixes.
- Use pytest with asyncio fixtures where necessary.
- If adding integration tests that depend on MongoDB or Redis, rely on existing fixtures in `tests/conftest.py`.

## Git Commit Guidelines
- Write clear, present-tense commit messages (e.g., "Add authorize middleware contract").
- Reference related issues in the PR description using `Fixes #<number>` when applicable.

## Issue Process
- Search open issues before filing new ones.
- When reporting bugs, include reproduction steps, expected behavior, actual results, and environment details.
- For feature requests, describe the use case and how it aligns with FastApp principles.

## Pull Requests
- Update documentation when behavior changes.
- Maintain backwards compatibility whenever reasonable.
- Include test results in the PR description (`pytest`, `mypy`).
- Expect a review focused on clarity, performance, and maintainability.

## Community Standards
- Follow the project's [Code of Conduct](./CODE_OF_CONDUCT.md).
- Be respectful, concise, and supportive.

We appreciate your contributions and look forward to building a stellar framework together.

