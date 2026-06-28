# TX-Packages Developer Guide

## Contributing

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/tx-packages.git
cd tx-packages

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Project Structure

```
tx-packages/
|-- builders/           # Core build framework (Python)
|   |-- __init__.py
|   |-- config.py       # Build configuration
|   |-- recipe.py       # Recipe parser
|   |-- dependency.py   # Dependency resolver
|   |-- downloader.py   # Source downloader
|   |-- builder.py      # Package builder
|   |-- packager.py     # Package generator
|   |-- bootstrap.py    # Bootstrap generator
|   |-- repository.py   # Repository generator
|   |-- version.py      # Semantic version parser
|-- python/
|   |-- tx_packages/    # CLI entry point
|       |-- __init__.py
|       |-- __main__.py
|-- recipes/            # Package recipes
|-- patches/            # Source patches
|-- tests/              # Test suite
|-- docs/               # Documentation
|-- .github/
|   |-- workflows/      # CI/CD pipelines
|-- configs/            # Configuration templates
|-- scripts/            # Utility scripts
```

## Adding a New Recipe

### 1. Create Recipe File

Create `recipes/<package-name>.recipe`:

```
name = mypackage
version = 1.0.0
category = mycategory
description = My awesome package
homepage = https://example.com
license = MIT
build_style = gnu

source =
    https://example.com/mypackage-1.0.0.tar.gz    sha256:abc123...

depends =
    libfoo
    libbar

makedepends =
    cmake
```

### 2. Add Patches (if needed)

```bash
mkdir -p patches/mypackage
# Copy patch files
cp fix-android.patch patches/mypackage/
```

Update recipe:
```
patches =
    fix-android.patch
```

### 3. Test Recipe

```bash
# Validate recipe
python3 -m tx_packages info mypackage

# Build package
python3 -m tx_packages build --recipe mypackage

# Check output
ls -la packages/mypackage/
```

### 4. Test Dependencies

```bash
# Check dependency resolution
python3 -c "
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver
parser = RecipeParser('recipes')
recipes = parser.load_all()
resolver = DependencyResolver(recipes)
order = resolver.resolve()
print('Build order:', order)
"
```

## Recipe Categories

When adding a new category, update:
1. Recipe `category` field
2. `docs/recipe-specification.md` category table
3. `python/tx_packages/__main__.py` list command filters

## Build Framework Extension

### Adding a New Build Style

Edit `builders/builder.py`:

```python
def _configure_newstyle(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
    """Configure using NewBuildSystem."""
    build_dir = source_dir / (recipe.build_dir if recipe.build_dir != "." else "build")
    build_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = ["newbuild", "configure", str(source_dir)]
    cmd.extend(recipe.configure_args)
    self._run_command(cmd, build_dir, env)
    
    return build_dir
```

Update `configure_args` handling in `_configure()`:

```python
elif build_style == "newstyle":
    return self._configure_newstyle(recipe, source_dir, env)
```

### Adding a New Architecture

Edit `builders/config.py`:

```python
@dataclass
class BuildConfig:
    target_arch: str = "aarch64"
    target_triple: str = "aarch64-linux-android"
    target_abi: str = "arm64-v8a"
```

Add architecture detection:

```python
def _setup_flags(self) -> None:
    if self.target_arch == "aarch64":
        arch_flags = ["-march=armv8-a"]
    elif self.target_arch == "x86_64":
        arch_flags = ["-march=x86-64"]
    # ...
```

## Testing Guidelines

### Writing Tests

```python
# tests/test_mypackage.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.recipe import RecipeParser

class TestMyPackage:
    def test_recipe_parses(self):
        parser = RecipeParser("recipes")
        recipe = parser.get_recipe("mypackage")
        assert recipe is not None
        assert recipe.version == "1.0.0"
    
    def test_build_succeeds(self, tmp_path):
        # Build test
        pass
```

### Running Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Specific test file
python3 -m pytest tests/test_recipe_parser.py -v

# With coverage
python3 -m pytest tests/ --cov=builders --cov-report=html
```

## Code Style

### Python

- PEP 8 compliant
- Type hints on all public functions
- Docstrings in Google format
- Maximum line length: 100 characters

### Recipe Files

- Lowercase package names
- Consistent indentation (4 spaces)
- Alphabetically sorted dependencies
- SHA-256 checksums for all sources

## Debugging

### Enable Debug Logging

```bash
python3 -m tx_packages build --recipe mypackage -v
```

### Inspect Build Artifacts

```bash
ls -la artifacts/mypackage/
cat artifacts/mypackage/.build.log 2>/dev/null || true
```

### Manual Build Steps

```bash
# Extract and configure manually
python3 -c "
from builders.config import BuildConfig
from builders.recipe import RecipeParser
from builders.builder import PackageBuilder

config = BuildConfig()
parser = RecipeParser(config.recipes_dir)
recipe = parser.get_recipe('mypackage')

builder = PackageBuilder(config)
builder._download_sources(recipe)
source_dir = builder._extract_sources(recipe)
builder._apply_patches(recipe, source_dir)

print(f'Source directory: {source_dir}')
print(f'Run: cd {source_dir} && ./configure && make')
"
```

## Release Process

### Versioning

TX-Packages follows Semantic Versioning:
- MAJOR: Breaking changes to recipe format or build system
- MINOR: New features, new packages
- PATCH: Bug fixes, recipe updates

### Creating a Release

1. Update version in `builders/__init__.py`
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v1.2.3 -m "Release v1.2.3"`
4. Push tag: `git push origin v1.2.3`
5. GitHub Actions automatically builds and publishes

### Pre-release Checklist

- [ ] All tests pass
- [ ] Recipe validation passes
- [ ] Dependencies resolve without errors
- [ ] Bootstrap generates successfully
- [ ] Repository metadata is valid
- [ ] Documentation is updated
- [ ] CHANGELOG is updated

## Getting Help

- Open an issue on GitHub
- Join the TX Linux community
- Check existing documentation in `docs/`
