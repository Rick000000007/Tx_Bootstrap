"""
Recipe Parser Tests

Tests for recipe parsing, validation, and loading.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.recipe import Recipe, RecipeParser, SourceDefinition
from builders.version import SemanticVersion


class TestRecipeParsing:
    """Test recipe file parsing."""

    def test_parse_basic_recipe(self, tmp_path):
        """Test parsing a basic recipe file."""
        recipe_file = tmp_path / "test.recipe"
        recipe_file.write_text("""
name = testpkg
version = 1.0.0
category = test
description = A test package
homepage = https://example.com
license = MIT
build_style = gnu

source =
    https://example.com/testpkg-1.0.0.tar.gz    abc123def456

depends =
    libfoo
    libbar
""")
        parser = RecipeParser(tmp_path)
        recipe = parser.parse_file(recipe_file)

        assert recipe.name == "testpkg"
        assert recipe.version == "1.0.0"
        assert recipe.category == "test"
        assert recipe.build_style == "gnu"
        assert len(recipe.depends) == 2
        assert "libfoo" in recipe.depends
        assert "libbar" in recipe.depends

    def test_parse_recipe_with_all_fields(self, tmp_path):
        """Test parsing a recipe with all optional fields."""
        recipe_file = tmp_path / "full.recipe"
        recipe_file.write_text("""
name = fullpkg
version = 2.1.0
epoch = 1
release = 3
category = devel
description = A full-featured test package with all fields
homepage = https://full.example.com
license = GPL-3.0-or-later
maintainer = Test <test@example.com>
upstream_author = John Doe
build_style = cmake
build_dir = build

source =
    https://example.com/fullpkg-2.1.0.tar.xz    sha256abcdef123456

source =
    https://example.com/patch-fix.diff    sha256patch789

depends =
    libfoo
    libbar

makedepends =
    cmake
    pkg-config

checkdepends =
    pytest

conflicts =
    oldpkg

provides =
    fullpkg-dev

replaces =
    oldfullpkg

recommends =
    fullpkg-doc

configure_args =
    --enable-feature-x
    --with-backend=auto

cmake_args =
    -DENABLE_TESTS=ON
    -DBUILD_SHARED_LIBS=ON

patches =
    fix-android-build.patch
    fix-bionic-compat.patch

env_vars =
    CUSTOM_VAR=value1
    ANOTHER_VAR=value2
""")
        parser = RecipeParser(tmp_path)
        recipe = parser.parse_file(recipe_file)

        assert recipe.name == "fullpkg"
        assert recipe.version == "2.1.0"
        assert recipe.epoch == 1
        assert recipe.release == 3
        assert recipe.category == "devel"
        assert recipe.maintainer == "Test <test@example.com>"
        assert len(recipe.depends) == 2
        assert len(recipe.makedepends) == 2
        assert len(recipe.conflicts) == 1
        assert len(recipe.provides) == 1
        assert len(recipe.patches) == 2
        assert len(recipe.env_vars) == 2

    def test_version_parsing(self):
        """Test version string parsing in recipes."""
        versions = [
            ("1.0.0", 1, 0, 0, None),
            ("2.1.3", 2, 1, 3, None),
            ("1.0.0-alpha", 1, 0, 0, "alpha"),
            ("1.0.0-beta.1", 1, 0, 0, "beta.1"),
            ("v1.2.3", 1, 2, 3, None),
        ]

        for ver_str, major, minor, patch, pre in versions:
            sv = SemanticVersion.parse(ver_str)
            assert sv.major == major, f"{ver_str}: major mismatch"
            assert sv.minor == minor, f"{ver_str}: minor mismatch"
            assert sv.patch == patch, f"{ver_str}: patch mismatch"
            assert sv.prerelease == pre, f"{ver_str}: prerelease mismatch"


class TestRecipeValidation:
    """Test recipe validation."""

    def test_missing_name(self, tmp_path):
        """Test that missing name raises error."""
        recipe_file = tmp_path / "bad.recipe"
        recipe_file.write_text("""
version = 1.0.0
build_style = gnu

source =
    https://example.com/test.tar.gz    abc123
""")
        parser = RecipeParser(tmp_path)
        with pytest.raises(ValueError, match="name"):
            parser.parse_file(recipe_file)

    def test_missing_version(self, tmp_path):
        """Test that missing version raises error."""
        recipe_file = tmp_path / "bad.recipe"
        recipe_file.write_text("""
name = testpkg
build_style = gnu

source =
    https://example.com/test.tar.gz    abc123
""")
        parser = RecipeParser(tmp_path)
        with pytest.raises(ValueError, match="version"):
            parser.parse_file(recipe_file)

    def test_valid_meta_recipe(self, tmp_path):
        """Test that meta packages don't need sources."""
        recipe_file = tmp_path / "meta.recipe"
        recipe_file.write_text("""
name = metapkg
version = 1.0.0
category = meta
description = A meta package
homepage = https://example.com
license = MIT
build_style = meta
""")
        parser = RecipeParser(tmp_path)
        recipe = parser.parse_file(recipe_file)
        assert recipe.name == "metapkg"
        assert recipe.build_style == "meta"


class TestRecipeLoading:
    """Test loading recipes from directory."""

    def test_load_all_recipes(self, tmp_path):
        """Test loading all recipes from a directory."""
        # Create multiple recipe files
        (tmp_path / "pkg1.recipe").write_text("""
name = pkg1
version = 1.0.0
category = test
description = Package 1
homepage = https://example.com
license = MIT
build_style = gnu

source =
    https://example.com/pkg1-1.0.0.tar.gz    abc123
""")
        (tmp_path / "pkg2.recipe").write_text("""
name = pkg2
version = 2.0.0
category = test
description = Package 2
homepage = https://example.com
license = MIT
build_style = cmake

source =
    https://example.com/pkg2-2.0.0.tar.gz    def456
""")

        parser = RecipeParser(tmp_path)
        recipes = parser.load_all()

        assert len(recipes) == 2
        assert "pkg1" in recipes
        assert "pkg2" in recipes
        assert recipes["pkg1"].version == "1.0.0"
        assert recipes["pkg2"].version == "2.0.0"

    def test_load_from_subdirectory(self, tmp_path):
        """Test loading recipes from subdirectories."""
        subdir = tmp_path / "group1"
        subdir.mkdir()
        (subdir / "recipe").write_text("""
name = grouped
version = 1.0.0
category = test
description = Grouped package
homepage = https://example.com
license = MIT
build_style = gnu

source =
    https://example.com/grouped-1.0.0.tar.gz    abc123
""")

        parser = RecipeParser(tmp_path)
        recipes = parser.load_all()

        assert "grouped" in recipes


class TestRecipeProperties:
    """Test recipe computed properties."""

    def test_full_version(self):
        """Test full_version property with epoch."""
        recipe = Recipe(
            name="test",
            version="1.0.0",
            epoch=1,
            release=2,
        )
        assert recipe.full_version == "1:1.0.0-2"

    def test_full_version_no_epoch(self):
        """Test full_version without epoch."""
        recipe = Recipe(
            name="test",
            version="1.0.0",
            epoch=0,
            release=1,
        )
        assert recipe.full_version == "1.0.0-1"

    def test_dependencies(self):
        """Test dependency collection."""
        recipe = Recipe(
            name="test",
            version="1.0.0",
            depends=["liba", "libb"],
            makedepends=["cmake", "liba"],
        )
        all_deps = recipe.get_all_dependencies()
        assert "liba" in all_deps
        assert "libb" in all_deps
        assert "cmake" in all_deps
