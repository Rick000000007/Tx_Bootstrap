"""
Semantic Version Parser

Implements semantic versioning (SemVer 2.0.0) parsing and comparison
for TX-Packages version resolution.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class SemanticVersion:
    """Represents a semantic version: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]."""

    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: Optional[str] = field(default=None, compare=False)
    build: Optional[str] = field(default=None, compare=False)
    raw: str = field(default="", compare=False)

    # Version regex pattern
    VERSION_RE = re.compile(
        r'^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?(?:-(?P<prerelease>[0-9A-Za-z-.]+))?(?:\+(?P<build>[0-9A-Za-z-.]+))?$'
    )

    @classmethod
    def parse(cls, version_string: str) -> 'SemanticVersion':
        """Parse a version string into a SemanticVersion object."""
        if not version_string:
            return cls(0, 0, 0, raw=version_string)

        match = cls.VERSION_RE.match(version_string.strip())
        if not match:
            # Try to extract numeric prefix
            numeric_match = re.match(r'^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?', version_string)
            if numeric_match:
                major = int(numeric_match.group(1) or 0)
                minor = int(numeric_match.group(2) or 0)
                patch = int(numeric_match.group(3) or 0)
                remainder = version_string[numeric_match.end():]
                prerelease = remainder.lstrip('-') if remainder else None
                return cls(major, minor, patch, prerelease=prerelease, raw=version_string)
            raise ValueError(f"Invalid version string: {version_string}")

        groups = match.groupdict()
        major = int(groups['major'] or 0)
        minor = int(groups['minor'] or 0)
        patch = int(groups['patch'] or 0)
        prerelease = groups.get('prerelease')
        build = groups.get('build')

        return cls(major, minor, patch, prerelease=prerelease, build=build, raw=version_string)

    def __str__(self) -> str:
        """Convert to string representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __repr__(self) -> str:
        return f"SemanticVersion({str(self)})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            try:
                other = SemanticVersion.parse(str(other))
            except ValueError:
                return False
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch and
                self._compare_prerelease(self.prerelease, other.prerelease) == 0)

    def __lt__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            other = SemanticVersion.parse(str(other))

        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        return self._compare_prerelease(self.prerelease, other.prerelease) < 0

    def __le__(self, other) -> bool:
        return self == other or self < other

    def __gt__(self, other) -> bool:
        return not self <= other

    def __ge__(self, other) -> bool:
        return not self < other

    @staticmethod
    def _compare_prerelease(a: Optional[str], b: Optional[str]) -> int:
        """Compare two prerelease strings. None > any string (stable > prerelease)."""
        if a == b:
            return 0
        if a is None and b is not None:
            return 1  # stable > prerelease
        if a is not None and b is None:
            return -1  # prerelease < stable

        # Split by dots and compare
        a_parts = a.split('.')
        b_parts = b.split('.')

        for a_part, b_part in zip(a_parts, b_parts):
            # Numeric identifiers are compared as integers
            a_is_num = a_part.isdigit()
            b_is_num = b_part.isdigit()

            if a_is_num and b_is_num:
                a_int, b_int = int(a_part), int(b_part)
                if a_int != b_int:
                    return -1 if a_int < b_int else 1
            elif a_is_num:
                return -1  # numeric < alphanumeric
            elif b_is_num:
                return 1   # alphanumeric > numeric
            else:
                if a_part != b_part:
                    return -1 if a_part < b_part else 1

        # Longer prerelease has higher precedence
        return len(a_parts) - len(b_parts)

    def is_prerelease(self) -> bool:
        """Check if this is a prerelease version."""
        return self.prerelease is not None

    def is_stable(self) -> bool:
        """Check if this is a stable release."""
        return self.prerelease is None

    def satisfies(self, constraint: str) -> bool:
        """Check if this version satisfies a constraint string.

        Supports: =, ==, !=, >, >=, <, <=, ~>, ^, ~
        Examples: ">=1.2.0", "~>1.2.3", "^1.0.0", ">=2.0.0,<3.0.0"
        """
        if not constraint or constraint == '*':
            return True

        # Handle comma-separated constraints
        if ',' in constraint:
            parts = [p.strip() for p in constraint.split(',')]
            return all(self.satisfies(p) for p in parts)

        constraint = constraint.strip()

        # Handle range constraints
        if constraint.startswith('>='):
            try:
                other = SemanticVersion.parse(constraint[2:].strip())
                return self >= other
            except ValueError:
                return False
        elif constraint.startswith('<='):
            try:
                other = SemanticVersion.parse(constraint[2:].strip())
                return self <= other
            except ValueError:
                return False
        elif constraint.startswith('>'):
            try:
                other = SemanticVersion.parse(constraint[1:].strip())
                return self > other
            except ValueError:
                return False
        elif constraint.startswith('<'):
            try:
                other = SemanticVersion.parse(constraint[1:].strip())
                return self < other
            except ValueError:
                return False
        elif constraint.startswith('~>'):
            # Pessimistic constraint: ~>1.2.3 means >=1.2.3,<1.3.0
            try:
                other = SemanticVersion.parse(constraint[2:].strip())
                if self < other:
                    return False
                # Upper bound
                if other.minor is not None:
                    upper = SemanticVersion(other.major, other.minor + 1, 0)
                else:
                    upper = SemanticVersion(other.major + 1, 0, 0)
                return self < upper
            except ValueError:
                return False
        elif constraint.startswith('^'):
            # Caret constraint: ^1.2.3 means >=1.2.3,<2.0.0
            try:
                other = SemanticVersion.parse(constraint[1:].strip())
                if self < other:
                    return False
                upper = SemanticVersion(other.major + 1, 0, 0)
                return self < upper
            except ValueError:
                return False
        elif constraint.startswith('~'):
            # Tilde constraint: ~1.2.3 means >=1.2.3,<1.3.0
            try:
                other = SemanticVersion.parse(constraint[1:].strip())
                if self < other:
                    return False
                upper = SemanticVersion(other.major, other.minor + 1, 0)
                return self < upper
            except ValueError:
                return False
        elif constraint.startswith('==') or constraint.startswith('='):
            op_len = 2 if constraint.startswith('==') else 1
            try:
                other = SemanticVersion.parse(constraint[op_len:].strip())
                return self == other
            except ValueError:
                return False
        elif constraint.startswith('!='):
            try:
                other = SemanticVersion.parse(constraint[2:].strip())
                return self != other
            except ValueError:
                return True
        else:
            # Bare version = exact match
            try:
                other = SemanticVersion.parse(constraint)
                return self == other
            except ValueError:
                return False

    def bump_major(self) -> 'SemanticVersion':
        """Return a new version with incremented major."""
        return SemanticVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> 'SemanticVersion':
        """Return a new version with incremented minor."""
        return SemanticVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> 'SemanticVersion':
        """Return a new version with incremented patch."""
        return SemanticVersion(self.major, self.minor, self.patch + 1)
