"""
Dependency Resolver Tests

Tests for dependency resolution, cycle detection, and build ordering.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.recipe import Recipe
from builders.dependency import DependencyResolver, DependencyError


class TestDependencyResolution:
    """Test dependency resolution."""

    def test_simple_resolution(self):
        """Test resolving dependencies for a simple graph."""
        recipes = {
            "a": Recipe(name="a", version="1.0.0", depends=["b"]),
            "b": Recipe(name="b", version="1.0.0", depends=["c"]),
            "c": Recipe(name="c", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve()

        assert order.index("c") < order.index("b")
        assert order.index("b") < order.index("a")

    def test_multiple_dependencies(self):
        """Test package with multiple dependencies."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", depends=["liba", "libb", "libc"]),
            "liba": Recipe(name="liba", version="1.0.0"),
            "libb": Recipe(name="libb", version="1.0.0"),
            "libc": Recipe(name="libc", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve()

        assert order.index("liba") < order.index("app")
        assert order.index("libb") < order.index("app")
        assert order.index("libc") < order.index("app")

    def test_shared_dependencies(self):
        """Test packages sharing common dependencies."""
        recipes = {
            "app1": Recipe(name="app1", version="1.0.0", depends=["liba", "libb"]),
            "app2": Recipe(name="app2", version="1.0.0", depends=["libb", "libc"]),
            "liba": Recipe(name="liba", version="1.0.0"),
            "libb": Recipe(name="libb", version="1.0.0"),
            "libc": Recipe(name="libc", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve()

        # Dependencies come before apps
        assert order.index("libb") < order.index("app1")
        assert order.index("libb") < order.index("app2")

    def test_cycle_detection(self):
        """Test cycle detection raises error."""
        recipes = {
            "a": Recipe(name="a", version="1.0.0", depends=["b"]),
            "b": Recipe(name="b", version="1.0.0", depends=["c"]),
            "c": Recipe(name="c", version="1.0.0", depends=["a"]),
        }

        resolver = DependencyResolver(recipes)
        with pytest.raises(DependencyError):
            resolver.resolve()

    def test_self_dependency(self):
        """Test that self-dependency is handled."""
        recipes = {
            "a": Recipe(name="a", version="1.0.0", depends=["a"]),
        }

        resolver = DependencyResolver(recipes)
        # Should not raise - self dependency is filtered
        order = resolver.resolve()
        assert order == ["a"]

    def test_empty_recipes(self):
        """Test with empty recipe set."""
        resolver = DependencyResolver({})
        order = resolver.resolve()
        assert order == []

    def test_parallel_groups(self):
        """Test parallel build groups."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", depends=["liba", "libb"]),
            "liba": Recipe(name="liba", version="1.0.0", depends=["base"]),
            "libb": Recipe(name="libb", version="1.0.0", depends=["base"]),
            "base": Recipe(name="base", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        resolver.resolve()
        groups = resolver.get_parallel_groups()

        # First group should only contain base
        assert "base" in groups[0]
        # Second group should contain liba and libb (parallel)
        assert any("liba" in g and "libb" in g for g in groups)


class TestBuildLevels:
    """Test build level computation."""

    def test_build_levels(self):
        """Test depth computation."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", depends=["lib"]),
            "lib": Recipe(name="lib", version="1.0.0", depends=["base"]),
            "base": Recipe(name="base", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        resolver.resolve()

        assert resolver.get_package_depth("base") == 0
        assert resolver.get_package_depth("lib") == 1
        assert resolver.get_package_depth("app") == 2

    def test_build_levels_complex(self):
        """Test depth with complex graph."""
        recipes = {
            "a": Recipe(name="a", version="1.0.0", depends=["b", "c"]),
            "b": Recipe(name="b", version="1.0.0", depends=["d"]),
            "c": Recipe(name="c", version="1.0.0", depends=["d"]),
            "d": Recipe(name="d", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        resolver.resolve()

        assert resolver.get_package_depth("d") == 0
        assert resolver.get_package_depth("b") == 1
        assert resolver.get_package_depth("c") == 1
        assert resolver.get_package_depth("a") == 2


class TestMissingDependencies:
    """Test handling of missing dependencies."""

    def test_missing_dependency(self):
        """Test that missing dependencies are reported."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", depends=["missing"]),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve()

        assert len(resolver.errors) > 0
        assert any("missing" in e for e in resolver.errors)

    def test_missing_build_dependency(self):
        """Test missing build-only dependency."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", makedepends=["missing"]),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve()

        assert len(resolver.errors) > 0


class TestTargetPackages:
    """Test targeted resolution."""

    def test_target_subset(self):
        """Test resolving for specific packages."""
        recipes = {
            "app": Recipe(name="app", version="1.0.0", depends=["lib"]),
            "lib": Recipe(name="lib", version="1.0.0", depends=["base"]),
            "base": Recipe(name="base", version="1.0.0"),
            "other": Recipe(name="other", version="1.0.0"),
        }

        resolver = DependencyResolver(recipes)
        order = resolver.resolve(["app"])

        assert "app" in order
        assert "lib" in order
        assert "base" in order
        # other is not needed for app
        assert "other" not in order
