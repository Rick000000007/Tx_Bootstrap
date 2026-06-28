#!/usr/bin/env python3
"""
TX-Packages Build System CLI

Usage:
    python -m tx_packages build [--recipe <name>] [--force]
    python -m tx_packages bootstrap [--packages <names>]
    python -m tx_packages repository [--output <dir>]
    python -m tx_packages list [--category <name>]
    python -m tx_packages info <package>
    python -m tx_packages clean [--cache] [--sources] [--downloads]
    python -m tx_packages test [--verbose]
"""

import sys
import os
import json
import logging
import argparse
import shutil
from pathlib import Path
from typing import List, Optional

# Add builders to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "builders"))

from builders.config import BuildConfig
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver, DependencyError
from builders.builder import PackageBuilder, BuildError
from builders.packager import PackageGenerator
from builders.bootstrap import BootstrapGenerator
from builders.repository import RepositoryGenerator

logger = logging.getLogger("tx_packages")


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def cmd_build(args: argparse.Namespace) -> int:
    """Build packages command."""
    config = BuildConfig()
    parser = RecipeParser(config.recipes_dir)
    recipes = parser.load_all()

    if not recipes:
        logger.error("No recipes found")
        return 1

    # Determine which packages to build
    if args.recipe:
        target_packages = args.recipe
        for pkg_name in target_packages:
            if pkg_name not in recipes:
                logger.error(f"Recipe not found: {pkg_name}")
                return 1
    else:
        target_packages = list(recipes.keys())

    # Resolve dependencies
    try:
        resolver = DependencyResolver(recipes)
        build_order = resolver.resolve(target_packages if args.recipe else None)
    except DependencyError as e:
        logger.error(f"Dependency resolution failed: {e}")
        return 1

    logger.info(f"Build order ({len(build_order)} packages):")
    for i, pkg_name in enumerate(build_order, 1):
        logger.info(f"  {i}. {pkg_name}")

    # Build packages
    builder = PackageBuilder(config)
    packager = PackageGenerator(config)

    success_count = 0
    failed_packages = []

    for i, pkg_name in enumerate(build_order, 1):
        recipe = recipes[pkg_name]
        logger.info(f"[{i}/{len(build_order)}] Building {pkg_name}...")

        try:
            result = builder.build(recipe, force_rebuild=args.force)
            if result.success:
                logger.info(f"  -> Build successful ({result.build_time:.1f}s)")

                # Generate package
                if result.install_prefix:
                    pkg_path = packager.generate(recipe, result.install_prefix)
                    logger.info(f"  -> Package: {pkg_path}")

                success_count += 1
            else:
                logger.error(f"  -> Build failed: {result.error}")
                failed_packages.append(pkg_name)
        except BuildError as e:
            logger.error(f"  -> Build error: {e}")
            failed_packages.append(pkg_name)
        except Exception as e:
            logger.error(f"  -> Unexpected error: {e}")
            failed_packages.append(pkg_name)

    logger.info(f"Build complete: {success_count}/{len(build_order)} succeeded")
    if failed_packages:
        logger.warning(f"Failed packages: {', '.join(failed_packages)}")
        return 1

    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Generate bootstrap command."""
    config = BuildConfig()
    parser = RecipeParser(config.recipes_dir)
    recipes = parser.load_all()

    if not recipes:
        logger.error("No recipes found")
        return 1

    # Determine packages for bootstrap
    generator = BootstrapGenerator(config)
    try:
        if args.packages:
            target_packages = args.packages.split(',')
            bootstrap_recipes = [recipes[p] for p in target_packages if p in recipes]
            bootstrap_path = generator.generate(bootstrap_recipes, config.packages_dir, "bootstrap")
            logger.info(f"Bootstrap generated: {bootstrap_path}")
        else:
            # Generate both standard and root bootstraps
            resolver = DependencyResolver(recipes)

            # Resolve standard bootstrap packages recursively
            std_targets = [p for p in config.bootstrap_base_packages if p in recipes]
            try:
                std_names = resolver.resolve(std_targets)
                standard_recipes = [recipes[name] for name in std_names if name in recipes and name not in config.root_packages]
            except Exception as e:
                logger.warning(f"Failed to resolve standard bootstrap dependencies: {e}. Falling back to list.")
                standard_recipes = [recipes[p] for p in config.bootstrap_base_packages if p in recipes]

            # Resolve root bootstrap packages recursively
            root_targets = [p for p in config.root_packages if p in recipes]
            try:
                root_names = resolver.resolve(root_targets)
                root_recipes = [recipes[name] for name in root_names if name in recipes]
            except Exception as e:
                logger.warning(f"Failed to resolve root bootstrap dependencies: {e}. Falling back to list.")
                root_recipes = [recipes[p] for p in config.root_packages if p in recipes]

            path_std = generator.generate(standard_recipes, config.packages_dir, "bootstrap")
            logger.info(f"Standard Bootstrap generated: {path_std}")

            path_root = generator.generate(root_recipes, config.packages_dir, "bootstrap-root")
            logger.info(f"Root Bootstrap generated: {path_root}")
    except Exception as e:
        logger.error(f"Bootstrap generation failed: {e}")
        return 1

    return 0


def cmd_repository(args: argparse.Namespace) -> int:
    """Generate repository command."""
    config = BuildConfig()
    parser = RecipeParser(config.recipes_dir)
    recipes = parser.load_all()

    if not recipes:
        logger.error("No recipes found")
        return 1

    generator = RepositoryGenerator(config)
    try:
        if args.output:
            repo_dir = generator.generate(list(recipes.values()), Path(args.output))
            logger.info(f"Repository generated: {repo_dir}")
        else:
            # Generate separate main and root repositories
            standard_recipes = [r for r in recipes.values() if r.name not in config.root_packages]
            root_recipes = [r for r in recipes.values() if r.name in config.root_packages]

            # Main repository
            repo_std = generator.generate(standard_recipes, config.repository_dir)
            logger.info(f"Standard Repository generated: {repo_std}")

            # Root repository
            repo_root = generator.generate(root_recipes, config.repository_dir.parent / "repository-root")
            logger.info(f"Root Repository generated: {repo_root}")
    except Exception as e:
        logger.error(f"Repository generation failed: {e}")
        return 1

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List packages command."""
    config = BuildConfig()
    parser = RecipeParser(config.recipes_dir)
    recipes = parser.load_all()

    if not recipes:
        print("No recipes found")
        return 1

    # Filter by category if specified
    if args.category:
        filtered = {k: v for k, v in recipes.items() if v.category == args.category}
    else:
        filtered = recipes

    # Group by category
    by_category = {}
    for name, recipe in filtered.items():
        cat = recipe.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(recipe)

    print(f"\nTX-Packages: {len(filtered)} packages")
    print("=" * 60)

    for category in sorted(by_category.keys()):
        recipes_in_cat = by_category[category]
        print(f"\n[{category}] ({len(recipes_in_cat)} packages)")
        for recipe in sorted(recipes_in_cat, key=lambda r: r.name):
            print(f"  {recipe.name:<20} {recipe.full_version:<20} {recipe.description[:40]}")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show package info command."""
    config = BuildConfig()
    parser = RecipeParser(config.recipes_dir)
    recipe = parser.get_recipe(args.package)

    if not recipe:
        print(f"Package not found: {args.package}")
        return 1

    print(f"\nPackage: {recipe.name}")
    print("=" * 60)
    print(f"  Version:      {recipe.full_version}")
    print(f"  Category:     {recipe.category}")
    print(f"  Description:  {recipe.description}")
    print(f"  Homepage:     {recipe.homepage}")
    print(f"  License:      {recipe.license}")
    print(f"  Build Style:  {recipe.build_style}")
    print(f"  Maintainer:   {recipe.maintainer}")

    if recipe.depends:
        print(f"\n  Dependencies:")
        for dep in recipe.depends:
            print(f"    - {dep}")

    if recipe.makedepends:
        print(f"\n  Build Dependencies:")
        for dep in recipe.makedepends:
            print(f"    - {dep}")

    if recipe.sources:
        print(f"\n  Sources:")
        for src in recipe.sources:
            print(f"    - {src.url}")

    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean build artifacts command."""
    config = BuildConfig()
    cleaned = []

    if args.all or args.cache:
        if config.cache_dir.exists():
            shutil.rmtree(config.cache_dir)
            config.cache_dir.mkdir(parents=True, exist_ok=True)
            cleaned.append("cache")

    if args.all or args.sources:
        if config.sources_dir.exists():
            shutil.rmtree(config.sources_dir)
            config.sources_dir.mkdir(parents=True, exist_ok=True)
            cleaned.append("sources")

    if args.all or args.downloads:
        if config.downloads_dir.exists():
            shutil.rmtree(config.downloads_dir)
            config.downloads_dir.mkdir(parents=True, exist_ok=True)
            cleaned.append("downloads")

    if args.all or args.artifacts:
        if config.artifacts_dir.exists():
            shutil.rmtree(config.artifacts_dir)
            config.artifacts_dir.mkdir(parents=True, exist_ok=True)
            cleaned.append("artifacts")

    if args.all or args.packages:
        if config.packages_dir.exists():
            shutil.rmtree(config.packages_dir)
            config.packages_dir.mkdir(parents=True, exist_ok=True)
            cleaned.append("packages")

    if cleaned:
        logger.info(f"Cleaned: {', '.join(cleaned)}")
    else:
        logger.info("Nothing to clean")

    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Run tests command."""
    import subprocess

    test_dir = Path(__file__).parent.parent.parent / "tests"
    if not test_dir.exists():
        logger.error("Tests directory not found")
        return 1

    # Run pytest
    pytest_args = ["pytest", "-v" if args.verbose else "", str(test_dir)]
    pytest_args = [a for a in pytest_args if a]

    try:
        result = subprocess.run(pytest_args)
        return result.returncode
    except FileNotFoundError:
        logger.error("pytest not found. Install with: pip install pytest")
        return 1


def cmd_full_build(args: argparse.Namespace) -> int:
    """Run complete build pipeline."""
    logger.info("=" * 60)
    logger.info("TX-Packages Full Build Pipeline")
    logger.info("=" * 60)

    # Step 1: Build all packages
    logger.info("\n[Step 1/4] Building all packages...")
    ret = cmd_build(argparse.Namespace(recipe=None, force=args.force))
    if ret != 0 and not args.continue_on_error:
        return ret

    # Step 2: Generate packages
    logger.info("\n[Step 2/4] Packages already generated during build")

    # Step 3: Generate bootstrap
    logger.info("\n[Step 3/4] Generating bootstrap...")
    ret = cmd_bootstrap(argparse.Namespace(packages=None))
    if ret != 0 and not args.continue_on_error:
        return ret

    # Step 4: Generate repository
    logger.info("\n[Step 4/4] Generating repository...")
    ret = cmd_repository(argparse.Namespace(output=None))
    if ret != 0 and not args.continue_on_error:
        return ret

    logger.info("\n" + "=" * 60)
    logger.info("Full build pipeline completed successfully!")
    logger.info("=" * 60)

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="tx_packages",
        description="TX-Packages Build System for Android"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build packages")
    build_parser.add_argument("--recipe", "-r", nargs="+", help="Build specific recipes")
    build_parser.add_argument("--force", "-f", action="store_true", help="Force rebuild")

    # Bootstrap command
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Generate bootstrap image")
    bootstrap_parser.add_argument("--packages", "-p", help="Comma-separated package list")

    # Repository command
    repo_parser = subparsers.add_parser("repository", help="Generate package repository")
    repo_parser.add_argument("--output", "-o", help="Output directory")

    # List command
    list_parser = subparsers.add_parser("list", help="List available packages")
    list_parser.add_argument("--category", "-c", help="Filter by category")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show package information")
    info_parser.add_argument("package", help="Package name")

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean build artifacts")
    clean_parser.add_argument("--all", "-a", action="store_true", help="Clean everything")
    clean_parser.add_argument("--cache", action="store_true", help="Clean cache")
    clean_parser.add_argument("--sources", action="store_true", help="Clean sources")
    clean_parser.add_argument("--downloads", action="store_true", help="Clean downloads")
    clean_parser.add_argument("--artifacts", action="store_true", help="Clean artifacts")
    clean_parser.add_argument("--packages", action="store_true", help="Clean packages")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run test suite")
    test_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Full build command
    full_parser = subparsers.add_parser("full-build", help="Run complete build pipeline")
    full_parser.add_argument("--force", "-f", action="store_true", help="Force rebuild")
    full_parser.add_argument("--continue-on-error", "-k", action="store_true",
                            help="Continue on error")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        'build': cmd_build,
        'bootstrap': cmd_bootstrap,
        'repository': cmd_repository,
        'list': cmd_list,
        'info': cmd_info,
        'clean': cmd_clean,
        'test': cmd_test,
        'full-build': cmd_full_build,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
