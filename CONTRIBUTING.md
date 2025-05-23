# Contributing to Suna

Thank you for your interest in contributing to Suna! This document outlines the contribution process and guidelines.

## Contribution Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'feat(your_file): add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## Development Setup

For detailed setup instructions, please refer to:

- [Backend Development Setup](backend/README.md)
- [Frontend Development Setup](frontend/README.md)

## Code Style Guidelines

- Follow existing code style and patterns
- Use descriptive commit messages
- Keep PRs focused on a single feature or fix

## Running Tests

Continuous integration runs the test suite with `pytest`. You can run the same
tests locally before opening a pull request:

```bash
cd backend
pytest
```

`pytest` will discover tests under `backend/tests/` using the provided
configuration. Ensuring tests pass locally helps avoid CI failures.

## Reporting Issues

When reporting issues, please include:

- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Node/Docker versions, etc.)
- Relevant logs or screenshots
