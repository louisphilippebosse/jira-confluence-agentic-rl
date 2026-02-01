# Contributing to Jira-Confluence Agentic AI

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the community

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported
2. Open an issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. Open an issue describing:
   - The feature and its benefits
   - Proposed implementation
   - Alternative approaches considered

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Commit with clear messages (`git commit -m 'Add amazing feature'`)
7. Push to your fork (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/jira-confluence-agentic-rl.git
cd jira-confluence-agentic-rl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run locally
uvicorn app.main:app --reload
```

## Coding Standards

- Follow PEP 8 style guide
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Write tests for new features

## Testing

- Add tests for new features
- Ensure all tests pass before submitting PR
- Aim for good test coverage

## Documentation

- Update README.md for user-facing changes
- Add docstrings for new functions/classes
- Update API documentation if needed

## Commit Messages

Use clear, descriptive commit messages:

```
Add feature: Brief description

Detailed explanation of what changed and why.
Include any relevant issue numbers.
```

## Review Process

1. Maintainers will review your PR
2. Address feedback and update PR
3. Once approved, your PR will be merged

## Questions?

Feel free to open an issue for any questions!
