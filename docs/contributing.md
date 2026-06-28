# Contributing to TX-Packages

## Getting Started

1. Fork the repository
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/tx-packages.git
cd tx-packages
```

3. Create a feature branch:
```bash
git checkout -b feature/my-feature
```

## Types of Contributions

### New Packages

- Add a recipe file in `recipes/`
- Follow the [Recipe Specification](recipe-specification.md)
- Test the build locally
- Update documentation if needed

### Bug Fixes

- Fix the issue in the appropriate module
- Add a test case that reproduces the bug
- Update documentation if behavior changes

### Documentation

- Fix typos and improve clarity
- Add examples and use cases
- Update outdated information

### Build System Improvements

- Follow [Coding Standards](coding-standards.md)
- Add tests for new functionality
- Update relevant documentation

## Development Workflow

1. Make changes
2. Run tests:
```bash
python3 -m pytest tests/ -v
```

3. Validate recipes:
```bash
python3 -m tx_packages list
```

4. Commit changes:
```bash
git add .
git commit -m "Add feature: description"
```

5. Push and create a Pull Request

## Review Process

- All PRs require at least one review
- CI checks must pass
- Documentation must be updated

## Code of Conduct

- Be respectful and constructive
- Focus on the technical merits
- Help newcomers get started
