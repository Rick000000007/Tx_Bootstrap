"""
TX-Packages Build System

A production-grade Linux userspace build system for Android arm64-v8a.
"""

__version__ = "1.0.0"
__author__ = "TX-Packages Contributors"

from .config import BuildConfig
from .recipe import Recipe, RecipeParser
from .dependency import DependencyResolver
from .downloader import SourceDownloader
from .builder import PackageBuilder
from .packager import PackageGenerator
from .bootstrap import BootstrapGenerator
from .repository import RepositoryGenerator

__all__ = [
    "BuildConfig",
    "Recipe",
    "RecipeParser",
    "DependencyResolver",
    "SourceDownloader",
    "PackageBuilder",
    "PackageGenerator",
    "BootstrapGenerator",
    "RepositoryGenerator",
]
