"""
Recipe Parser Module

Parses TX-Packages build recipes from recipe files.
Recipes define how to download, build, and package upstream software.
"""

import os
import re
import ast
import json
import logging
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

from .version import SemanticVersion

logger = logging.getLogger(__name__)


@dataclass
class SourceDefinition:
    """Defines an upstream source."""
    url: str
    checksum: str  # sha256
    filename: Optional[str] = None
    mirror_urls: List[str] = field(default_factory=list)
    git_url: Optional[str] = None
    git_tag: Optional[str] = None
    git_depth: int = 1


@dataclass
class Recipe:
    """A TX-Packages build recipe."""

    # Identity
    name: str
    version: str
    epoch: int = 0
    release: int = 1
    category: str = "misc"

    # Metadata
    description: str = ""
    homepage: str = ""
    license: str = ""
    maintainer: str = ""
    upstream_author: str = ""

    # Source
    sources: List[SourceDefinition] = field(default_factory=list)

    # Dependencies
    depends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    checkdepends: List[str] = field(default_factory=list)
    optdepends: Dict[str, str] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    recommends: List[str] = field(default_factory=list)

    # Build configuration
    configure_args: List[str] = field(default_factory=list)
    make_args: List[str] = field(default_factory=list)
    check_args: List[str] = field(default_factory=list)
    cmake_args: List[str] = field(default_factory=list)
    meson_args: List[str] = field(default_factory=list)
    build_style: str = "gnu"  # gnu, cmake, meson, python, make, custom
    build_dir: str = "build"
    extract_dir: Optional[str] = None

    # Build environment
    env_vars: Dict[str, str] = field(default_factory=dict)
    pre_build_cmds: List[str] = field(default_factory=list)
    post_build_cmds: List[str] = field(default_factory=list)
    pre_install_cmds: List[str] = field(default_factory=list)
    post_install_cmds: List[str] = field(default_factory=list)

    # Patches
    patches: List[str] = field(default_factory=list)
    patch_args: List[str] = field(default_factory=lambda: ["-p1"])

    # Options
    strip_binaries: bool = True
    strip_static: bool = True
    strip_shared: bool = False
    static: bool = False
    shared: bool = True

    # Scriptlets (bash scripts)
    pre_install_script: str = ""
    post_install_script: str = ""
    pre_remove_script: str = ""
    post_remove_script: str = ""

    # File lists
    extra_files: List[str] = field(default_factory=list)
    backup_files: List[str] = field(default_factory=list)

    # Internal
    _recipe_path: Optional[Path] = field(default=None, repr=False)
    _parsed_version: Optional[SemanticVersion] = field(default=None, repr=False)

    @property
    def full_version(self) -> str:
        """Get the full version string including epoch and release."""
        if self.epoch > 0:
            return f"{self.epoch}:{self.version}-{self.release}"
        return f"{self.version}-{self.release}"

    @property
    def upstream_version(self) -> SemanticVersion:
        """Get parsed upstream version."""
        if self._parsed_version is None:
            self._parsed_version = SemanticVersion.parse(self.version)
        return self._parsed_version

    @property
    def pkg_filename(self) -> str:
        """Get the package filename."""
        if self.epoch > 0:
            return f"{self.name}-{self.epoch}_{self.version}-{self.release}.txpkg"
        return f"{self.name}-{self.version}-{self.release}.txpkg"

    @property
    def source_dir(self) -> str:
        """Get the expected source directory name."""
        if self.extract_dir:
            return self.extract_dir
        return f"{self.name}-{self.version}"

    def get_all_dependencies(self) -> Set[str]:
        """Get all runtime and build dependencies."""
        deps = set(self.depends)
        deps.update(self.makedepends)
        return deps

    def get_build_dependencies(self) -> Set[str]:
        """Get only build dependencies."""
        return set(self.makedepends)

    def get_runtime_dependencies(self) -> Set[str]:
        """Get only runtime dependencies."""
        return set(self.depends)

    def to_dict(self) -> Dict[str, Any]:
        """Convert recipe to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "epoch": self.epoch,
            "release": self.release,
            "category": self.category,
            "description": self.description,
            "homepage": self.homepage,
            "license": self.license,
            "full_version": self.full_version,
            "source_dir": self.source_dir,
            "pkg_filename": self.pkg_filename,
            "build_style": self.build_style,
            "sources": [
                {
                    "url": s.url,
                    "checksum": s.checksum,
                    "filename": s.filename,
                    "mirror_urls": s.mirror_urls,
                }
                for s in self.sources
            ],
            "depends": self.depends,
            "makedepends": self.makedepends,
            "checkdepends": self.checkdepends,
            "optdepends": self.optdepends,
            "conflicts": self.conflicts,
            "provides": self.provides,
            "replaces": self.replaces,
            "recommends": self.recommends,
            "configure_args": self.configure_args,
            "make_args": self.make_args,
            "cmake_args": self.cmake_args,
            "meson_args": self.meson_args,
            "patches": self.patches,
            "env_vars": self.env_vars,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert recipe to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class RecipeParser:
    """Parser for TX-Packages recipe files."""

    # Recipe file name pattern: <name>.recipe or <name>/recipe
    RECIPE_EXTENSIONS = ['.recipe', '.txrecipe']

    def __init__(self, recipes_dir: Path):
        self.recipes_dir = Path(recipes_dir)
        self._recipes: Dict[str, Recipe] = {}
        self._parse_errors: List[Tuple[str, str]] = []

    def parse_file(self, path: Path) -> Recipe:
        """Parse a single recipe file."""
        path = Path(path)
        logger.debug(f"Parsing recipe: {path}")

        content = path.read_text(encoding='utf-8')

        # Parse recipe file - simple key-value format with Python expressions
        data = self._parse_content(content, path)

        # Build Recipe object
        recipe = self._build_recipe(data, path)
        recipe._recipe_path = path

        # Validate
        self._validate_recipe(recipe)

        logger.info(f"Parsed recipe: {recipe.name} {recipe.full_version}")
        return recipe

    def _parse_content(self, content: str, path: Path) -> Dict[str, Any]:
        """Parse recipe file content into a dictionary."""
        data: Dict[str, Any] = {}
        current_key: Optional[str] = None
        current_lines: List[str] = []

        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # Check for key-value pair (key = value)
            if '=' in stripped and not line.startswith(' ') and not line.startswith('\t'):
                # Save previous key
                if current_key is not None:
                    data[current_key] = '\n'.join(current_lines)

                # Parse new key
                key, value = stripped.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.startswith("'")):
                    value = value[1:-1]

                current_key = key
                current_lines = [value]
            elif line.startswith(' ') or line.startswith('\t'):
                # Continuation of previous key
                if current_key is not None:
                    current_lines.append(stripped)
            else:
                # Save previous key and start new
                if current_key is not None:
                    data[current_key] = '\n'.join(current_lines)
                current_key = stripped
                current_lines = []

            i += 1

        # Save last key
        if current_key is not None:
            data[current_key] = '\n'.join(current_lines)

        return data

    def _build_recipe(self, data: Dict[str, Any], path: Path) -> Recipe:
        """Build a Recipe object from parsed data."""
        kwargs: Dict[str, Any] = {}

        # String fields
        for field_name in ['name', 'version', 'category', 'description', 'homepage',
                          'license', 'maintainer', 'upstream_author', 'build_style',
                          'build_dir', 'extract_dir', 'pre_install_script', 'post_install_script',
                          'pre_remove_script', 'post_remove_script']:
            if field_name in data:
                kwargs[field_name] = data[field_name].strip()

        # Integer fields
        for field_name in ['epoch', 'release']:
            if field_name in data:
                try:
                    kwargs[field_name] = int(data[field_name].strip())
                except ValueError:
                    pass

        # List fields
        for field_name in ['depends', 'makedepends', 'checkdepends', 'conflicts',
                          'provides', 'replaces', 'recommends', 'configure_args',
                          'make_args', 'check_args', 'cmake_args', 'meson_args',
                          'patches', 'patch_args', 'extra_files', 'backup_files',
                          'pre_build_cmds', 'post_build_cmds', 'pre_install_cmds',
                          'post_install_cmds']:
            if field_name in data:
                kwargs[field_name] = self._parse_list(data[field_name])

        # Dict fields
        if 'optdepends' in data:
            kwargs['optdepends'] = self._parse_dict(data['optdepends'])

        if 'env_vars' in data:
            kwargs['env_vars'] = self._parse_dict(data['env_vars'])

        # Sources
        if 'source' in data:
            kwargs['sources'] = self._parse_sources(data['source'], path.parent)

        # Boolean fields
        for field_name in ['strip_binaries', 'strip_static', 'strip_shared', 'static', 'shared']:
            if field_name in data:
                val = data[field_name].strip().lower()
                kwargs[field_name] = val in ('true', 'yes', '1', 'on')

        return Recipe(**kwargs)

    def _strip_quotes(self, s: str) -> str:
        """Strip outer quotes from a string or its value part if it contains '='."""
        s = s.strip()
        if '=' in s:
            k, v = s.split('=', 1)
            k = k.strip()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            return f"{k}={v}"
        else:
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                return s[1:-1]
            return s

    def _parse_list(self, value: str) -> List[str]:
        """Parse a newline-separated list."""
        items = []
        for line in value.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                items.append(self._strip_quotes(line))
        return items

    def _parse_dict(self, value: str) -> Dict[str, str]:
        """Parse key-value pairs."""
        result = {}
        for line in value.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                result[k] = v
        return result

    def _parse_sources(self, value: str, recipe_dir: Path) -> List[SourceDefinition]:
        """Parse source definitions."""
        sources = []
        for line in value.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) >= 2:
                url = parts[0]
                checksum = parts[1]
                filename = parts[2] if len(parts) > 2 else None

                mirror_urls = []
                git_url = None
                git_tag = None

                # Check for mirror URLs (lines starting with mirror:)
                # Not implemented in basic format

                sources.append(SourceDefinition(
                    url=url,
                    checksum=checksum,
                    filename=filename,
                    mirror_urls=mirror_urls,
                    git_url=git_url,
                    git_tag=git_tag,
                ))
            elif len(parts) == 1:
                # URL only - checksum will be verified later
                sources.append(SourceDefinition(url=parts[0], checksum=""))

        return sources

    def _validate_recipe(self, recipe: Recipe) -> None:
        """Validate a parsed recipe."""
        if not recipe.name:
            raise ValueError("Recipe must have a name")
        if not recipe.version:
            raise ValueError(f"Recipe {recipe.name} must have a version")
        if not recipe.sources and recipe.build_style != "meta":
            raise ValueError(f"Recipe {recipe.name} must have at least one source")

        # Validate version format
        try:
            SemanticVersion.parse(recipe.version)
        except ValueError as e:
            logger.warning(f"Recipe {recipe.name} has unusual version format: {recipe.version}")

    def load_all(self) -> Dict[str, Recipe]:
        """Load and parse all recipes from the recipes directory."""
        self._recipes = {}
        self._parse_errors = []

        if not self.recipes_dir.exists():
            logger.error(f"Recipes directory not found: {self.recipes_dir}")
            return self._recipes

        # Find all recipe files
        recipe_files = []
        for ext in self.RECIPE_EXTENSIONS:
            recipe_files.extend(self.recipes_dir.rglob(f"*{ext}"))

        # Also check for 'recipe' files in subdirectories
        for subdir in self.recipes_dir.iterdir():
            if subdir.is_dir():
                recipe_file = subdir / "recipe"
                if recipe_file.exists():
                    recipe_files.append(recipe_file)

        # Sort for deterministic loading
        recipe_files.sort(key=lambda p: p.name)

        logger.info(f"Found {len(recipe_files)} recipe files")

        for recipe_file in recipe_files:
            try:
                recipe = self.parse_file(recipe_file)
                self._recipes[recipe.name] = recipe
            except Exception as e:
                error_msg = str(e)
                self._parse_errors.append((str(recipe_file), error_msg))
                logger.error(f"Failed to parse {recipe_file}: {error_msg}")

        logger.info(f"Successfully loaded {len(self._recipes)} recipes")
        if self._parse_errors:
            logger.warning(f"Failed to parse {len(self._parse_errors)} recipes")

        return self._recipes

    def get_recipe(self, name: str) -> Optional[Recipe]:
        """Get a recipe by name."""
        if name in self._recipes:
            return self._recipes[name]
        # Try loading
        for ext in self.RECIPE_EXTENSIONS:
            recipe_file = self.recipes_dir / f"{name}{ext}"
            if recipe_file.exists():
                try:
                    recipe = self.parse_file(recipe_file)
                    self._recipes[recipe.name] = recipe
                    return recipe
                except Exception as e:
                    logger.error(f"Failed to parse {recipe_file}: {e}")
        return None

    @property
    def recipes(self) -> Dict[str, Recipe]:
        """Get all loaded recipes."""
        return self._recipes

    @property
    def parse_errors(self) -> List[Tuple[str, str]]:
        """Get parse errors."""
        return self._parse_errors
