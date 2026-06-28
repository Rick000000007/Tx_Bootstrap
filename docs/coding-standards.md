# TX-Packages Coding Standards

## Python

### Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Maximum line length: 100 characters
- Use 4 spaces for indentation
- Use single quotes for strings unless double quotes are needed

### Type Hints

All public functions must have type hints:

```python
def build_package(recipe: Recipe, force: bool = False) -> BuildResult:
    """Build a package from recipe."""
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def download_source(
    source: SourceDefinition,
    pkg_name: str,
    retries: int = 3,
) -> DownloadResult:
    """Download a source with retry and verification.

    Args:
        source: Source definition with URL and checksum
        pkg_name: Package name for display
        retries: Number of retry attempts

    Returns:
        DownloadResult with success status and file path

    Raises:
        DownloadError: If all download attempts fail
    """
```

### Error Handling

- Use custom exception classes
- Log errors with context
- Never silently ignore exceptions

```python
class BuildError(Exception):
    """Exception raised for build errors."""
    pass

try:
    result = builder.build(recipe)
except BuildError as e:
    logger.error(f"Build failed for {recipe.name}: {e}")
    raise
```

### Imports

Group imports in order:
1. Standard library
2. Third-party
3. Local modules

```python
import os
import sys
from pathlib import Path
from typing import Dict, List

import zstandard

from builders.config import BuildConfig
from builders.recipe import Recipe
```

## Recipe Files

### Format

- Use consistent indentation (4 spaces)
- Sort dependencies alphabetically
- Include SHA-256 checksums for all sources
- Use SPDX license identifiers

```
name = example
category = utilities
description = Example utility program
homepage = https://example.com
license = MIT

source =
    https://example.com/example-1.0.0.tar.gz    abc123def456...

depends =
    libfoo
    libbar
    zlib
```

### Naming

- Package names: lowercase, alphanumeric, hyphens
- Recipe files: `<name>.recipe`
- Patch files: descriptive, include bug reference if applicable

## Tests

### Structure

```python
class TestFeature:
    """Test feature X."""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly."""
        # Arrange
        input_data = ...

        # Act
        result = function(input_data)

        # Assert
        assert result == expected
```

### Naming

- Test files: `test_<module>.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<specific_behavior>`

## Git

### Commits

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues where applicable

```
Add support for meson build style

Implement meson build style configuration, compilation,
and installation in the package builder.

Closes #123
```

### Branches

- `main`: Production-ready code
- `develop`: Integration branch
- `feature/<name>`: Feature branches
- `fix/<name>`: Bug fix branches
