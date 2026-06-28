"""
Semantic Version Tests

Tests for semantic version parsing and comparison.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.version import SemanticVersion


class TestVersionParsing:
    """Test version string parsing."""

    def test_simple_version(self):
        """Parse simple MAJOR.MINOR.PATCH."""
        v = SemanticVersion.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_v_prefix(self):
        """Parse version with v prefix."""
        v = SemanticVersion.parse("v1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_prerelease(self):
        """Parse version with prerelease."""
        v = SemanticVersion.parse("1.0.0-alpha")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease == "alpha"

    def test_build_metadata(self):
        """Parse version with build metadata."""
        v = SemanticVersion.parse("1.0.0+build123")
        assert v.major == 1
        assert v.build == "build123"

    def test_full_version(self):
        """Parse version with prerelease and build."""
        v = SemanticVersion.parse("1.0.0-beta.1+exp.sha.5114f85")
        assert v.major == 1
        assert v.prerelease == "beta.1"
        assert v.build == "exp.sha.5114f85"

    def test_invalid_version(self):
        """Invalid version string raises ValueError."""
        with pytest.raises(ValueError):
            SemanticVersion.parse("not-a-version")

    def test_empty_string(self):
        """Empty string returns 0.0.0."""
        v = SemanticVersion.parse("")
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0

    def test_two_components(self):
        """Parse MAJOR.MINOR."""
        v = SemanticVersion.parse("1.2")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 0

    def test_one_component(self):
        """Parse MAJOR only."""
        v = SemanticVersion.parse("1")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0


class TestVersionComparison:
    """Test version comparison."""

    def test_equal(self):
        """Test equality."""
        assert SemanticVersion.parse("1.2.3") == SemanticVersion.parse("1.2.3")
        assert SemanticVersion.parse("1.2.3") == "1.2.3"

    def test_not_equal(self):
        """Test inequality."""
        assert SemanticVersion.parse("1.2.3") != SemanticVersion.parse("1.2.4")

    def test_less_than(self):
        """Test less than."""
        assert SemanticVersion.parse("1.0.0") < SemanticVersion.parse("2.0.0")
        assert SemanticVersion.parse("1.0.0") < SemanticVersion.parse("1.1.0")
        assert SemanticVersion.parse("1.0.0") < SemanticVersion.parse("1.0.1")

    def test_greater_than(self):
        """Test greater than."""
        assert SemanticVersion.parse("2.0.0") > SemanticVersion.parse("1.0.0")
        assert SemanticVersion.parse("1.1.0") > SemanticVersion.parse("1.0.0")
        assert SemanticVersion.parse("1.0.1") > SemanticVersion.parse("1.0.0")

    def test_prerelease_less_than_stable(self):
        """Prerelease is less than stable."""
        assert SemanticVersion.parse("1.0.0-alpha") < SemanticVersion.parse("1.0.0")
        assert SemanticVersion.parse("1.0.0-beta") < SemanticVersion.parse("1.0.0")

    def test_prerelease_comparison(self):
        """Compare prereleases."""
        assert SemanticVersion.parse("1.0.0-alpha") < SemanticVersion.parse("1.0.0-beta")
        assert SemanticVersion.parse("1.0.0-alpha.1") < SemanticVersion.parse("1.0.0-alpha.2")


class TestVersionConstraints:
    """Test version constraint satisfaction."""

    def test_exact_match(self):
        """Exact version constraint."""
        v = SemanticVersion.parse("1.2.3")
        assert v.satisfies("1.2.3")
        assert not v.satisfies("1.2.4")

    def test_greater_than(self):
        """Greater than constraint."""
        v = SemanticVersion.parse("2.0.0")
        assert v.satisfies(">1.0.0")
        assert not v.satisfies(">2.0.0")

    def test_greater_than_equal(self):
        """Greater than or equal constraint."""
        v = SemanticVersion.parse("2.0.0")
        assert v.satisfies(">=1.0.0")
        assert v.satisfies(">=2.0.0")
        assert not v.satisfies(">=3.0.0")

    def test_less_than(self):
        """Less than constraint."""
        v = SemanticVersion.parse("1.0.0")
        assert v.satisfies("<2.0.0")
        assert not v.satisfies("<1.0.0")

    def test_caret_constraint(self):
        """Caret (^) constraint."""
        v = SemanticVersion.parse("1.2.3")
        assert v.satisfies("^1.0.0")
        assert v.satisfies("^1.2.0")
        assert not v.satisfies("^2.0.0")

    def test_tilde_constraint(self):
        """Tilde (~) constraint."""
        v = SemanticVersion.parse("1.2.3")
        assert v.satisfies("~1.2.0")
        assert not v.satisfies("~1.3.0")

    def test_range_constraint(self):
        """Range constraint with comma."""
        v = SemanticVersion.parse("1.5.0")
        assert v.satisfies(">=1.0.0,<2.0.0")
        assert not v.satisfies(">=2.0.0,<3.0.0")

    def test_wildcard(self):
        """Wildcard constraint."""
        v = SemanticVersion.parse("1.2.3")
        assert v.satisfies("*")


class TestVersionBumping:
    """Test version bumping."""

    def test_bump_major(self):
        """Bump major version."""
        v = SemanticVersion.parse("1.2.3")
        bumped = v.bump_major()
        assert bumped.major == 2
        assert bumped.minor == 0
        assert bumped.patch == 0

    def test_bump_minor(self):
        """Bump minor version."""
        v = SemanticVersion.parse("1.2.3")
        bumped = v.bump_minor()
        assert bumped.major == 1
        assert bumped.minor == 3
        assert bumped.patch == 0

    def test_bump_patch(self):
        """Bump patch version."""
        v = SemanticVersion.parse("1.2.3")
        bumped = v.bump_patch()
        assert bumped.major == 1
        assert bumped.minor == 2
        assert bumped.patch == 4


class TestVersionProperties:
    """Test version properties."""

    def test_is_prerelease(self):
        """Test prerelease detection."""
        assert SemanticVersion.parse("1.0.0-alpha").is_prerelease()
        assert not SemanticVersion.parse("1.0.0").is_prerelease()

    def test_is_stable(self):
        """Test stable detection."""
        assert SemanticVersion.parse("1.0.0").is_stable()
        assert not SemanticVersion.parse("1.0.0-alpha").is_stable()

    def test_string_conversion(self):
        """Test string conversion."""
        assert str(SemanticVersion.parse("1.2.3")) == "1.2.3"
        assert str(SemanticVersion.parse("1.0.0-alpha")) == "1.0.0-alpha"
        assert str(SemanticVersion.parse("1.0.0+build")) == "1.0.0+build"
