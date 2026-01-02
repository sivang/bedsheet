# Contributing to Bedsheet Agents

Thank you for your interest in contributing to Bedsheet Agents! We welcome contributions of all kinds.

## Getting Started

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/bedsheet
   cd bedsheet
   ```

3. **Create a virtual environment**:
   ```bash
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```

4. **Install development dependencies**:
   ```bash
   uv pip install -e ".[dev]"
   ```

5. **Run tests** to make sure everything works:
   ```bash
   pytest -v
   ```

## Development Workflow

### Making Changes

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests first** (TDD encouraged):
   ```bash
   # Add tests to tests/
   pytest tests/test_your_feature.py -v
   ```

3. **Implement your changes**

4. **Run the full test suite**:
   ```bash
   pytest -v
   ```

5. **Format your code** (we use standard Python conventions):
   ```bash
   # Optional: install ruff for linting
   uv pip install ruff
   ruff check .
   ```

### Commit Messages

We follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

Examples:
```
feat: add support for custom memory backends
fix: handle tool timeout gracefully
docs: add multi-agent tutorial
```

### Pull Requests

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** on GitHub

3. **Describe your changes**:
   - What does this PR do?
   - Why is it needed?
   - How was it tested?

4. **Wait for review** - we'll respond as soon as we can!

## What We're Looking For

### Good First Issues

- Documentation improvements
- Additional examples
- Test coverage improvements
- Bug fixes

### Larger Contributions

Before starting major work, please open an issue to discuss:

- New features
- Architecture changes
- New integrations

This helps avoid duplicate work and ensures your contribution aligns with the project direction.

## Code Style

- **Type hints** - All public functions should have type hints
- **Docstrings** - Public classes and functions need docstrings
- **Tests** - New features need tests
- **Simplicity** - Prefer simple, readable code over clever code

## Testing

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest --cov=bedsheet -v
```

## Questions?

- Open an issue on GitHub
- Check existing issues and discussions

## License

By contributing, you agree that your contributions will be licensed under the Elastic License 2.0.

---

**Copyright © 2025-2026 Sivan Grünberg, [Vitakka Consulting](https://vitakka.co/)**
