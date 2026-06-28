"""
Dependency Resolver Module

Resolves package dependencies, detects cycles, and computes build order
topologically for parallel execution.
"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .recipe import Recipe

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """A node in the dependency graph."""
    recipe: Recipe
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    depth: int = 0


class DependencyResolver:
    """Resolves package dependencies and determines build order."""

    def __init__(self, recipes: Dict[str, Recipe]):
        self.recipes = recipes
        self._graph: Dict[str, DependencyNode] = {}
        self._build_order: List[str] = []
        self._errors: List[str] = []

    def resolve(self, target_packages: Optional[List[str]] = None) -> List[str]:
        """
        Resolve dependencies and return build order.

        Args:
            target_packages: If specified, only resolve for these packages.
                           Otherwise resolve for all packages.

        Returns:
            List of package names in build order (dependencies first).
        """
        self._graph = {}
        self._build_order = []
        self._errors = []

        # Determine packages to process
        if target_packages:
            packages_to_process = set(target_packages)
            # Add all dependencies
            for pkg_name in target_packages:
                deps = self._collect_all_dependencies(pkg_name)
                packages_to_process.update(deps)
        else:
            packages_to_process = set(self.recipes.keys())

        logger.info(f"Resolving dependencies for {len(packages_to_process)} packages")

        # Build dependency graph
        self._build_graph(packages_to_process)

        # Detect cycles
        cycles = self._detect_cycles()
        if cycles:
            for cycle in cycles:
                error_msg = f"Dependency cycle detected: {' -> '.join(cycle)}"
                self._errors.append(error_msg)
                logger.error(error_msg)
            raise DependencyError(f"Dependency cycles detected: {len(cycles)}")

        # Compute topological sort
        self._build_order = self._topological_sort()

        # Compute depths for parallel scheduling
        self._compute_depths()

        logger.info(f"Build order resolved: {len(self._build_order)} packages")
        return self._build_order

    def _collect_all_dependencies(self, pkg_name: str, collected: Optional[Set[str]] = None) -> Set[str]:
        """Recursively collect all dependencies for a package."""
        if collected is None:
            collected = set()

        if pkg_name in collected:
            return collected

        recipe = self.recipes.get(pkg_name)
        if not recipe:
            return collected

        for dep in recipe.get_all_dependencies():
            if dep not in collected:
                collected.add(dep)
                self._collect_all_dependencies(dep, collected)

        return collected

    def _build_graph(self, packages: Set[str]) -> None:
        """Build the dependency graph."""
        # Create nodes
        for pkg_name in packages:
            recipe = self.recipes.get(pkg_name)
            if recipe:
                self._graph[pkg_name] = DependencyNode(recipe=recipe)
            else:
                logger.warning(f"Recipe not found for package: {pkg_name}")

        # Connect dependencies
        for pkg_name, node in self._graph.items():
            for dep_name in node.recipe.get_all_dependencies():
                if dep_name in self._graph:
                    node.dependencies.add(dep_name)
                    self._graph[dep_name].dependents.add(pkg_name)
                elif dep_name in self.recipes:
                    # Dependency exists but not in current build set
                    logger.debug(f"Dependency {dep_name} of {pkg_name} not in build set")
                else:
                    # Missing dependency
                    error_msg = f"Package {pkg_name} depends on {dep_name} which has no recipe"
                    if error_msg not in self._errors:
                        self._errors.append(error_msg)
                        logger.error(error_msg)

    def _detect_cycles(self) -> List[List[str]]:
        """Detect dependency cycles using DFS."""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self._graph.get(node, DependencyNode(recipe=None)).dependencies:
                if dep not in visited:
                    dfs(dep)
                elif dep in rec_stack:
                    # Cycle detected
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    if cycle not in cycles:
                        cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in self._graph:
            if node not in visited:
                dfs(node)

        return cycles

    def _topological_sort(self) -> List[str]:
        """Compute topological sort using Kahn's algorithm."""
        # Calculate in-degree for each node
        in_degree = {pkg: len(node.dependencies) for pkg, node in self._graph.items()}

        # Start with nodes that have no dependencies
        queue = deque([pkg for pkg, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            # Sort for determinism
            queue = deque(sorted(queue))
            pkg = queue.popleft()
            result.append(pkg)

            # Remove this node from the graph
            for dependent in sorted(self._graph[pkg].dependents):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._graph):
            # This shouldn't happen if cycle detection passed
            remaining = set(self._graph.keys()) - set(result)
            logger.error(f"Topological sort incomplete. Remaining: {remaining}")
            raise DependencyError(f"Failed to resolve build order for: {remaining}")

        return result

    def _compute_depths(self) -> None:
        """Compute dependency depth for each package."""
        for pkg_name in self._build_order:
            node = self._graph[pkg_name]
            if node.dependencies:
                node.depth = max(
                    self._graph[dep].depth + 1
                    for dep in node.dependencies
                    if dep in self._graph
                )

    def get_build_levels(self) -> Dict[int, List[str]]:
        """
        Get packages grouped by build level for parallel execution.

        Returns:
            Dictionary mapping depth to list of package names.
        """
        levels: Dict[int, List[str]] = defaultdict(list)
        for pkg_name in self._build_order:
            node = self._graph[pkg_name]
            levels[node.depth].append(pkg_name)
        return dict(levels)

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get groups of packages that can be built in parallel.

        Returns:
            List of package name groups, each group can be built in parallel.
        """
        levels = self.get_build_levels()
        return [levels[i] for i in sorted(levels.keys())]

    def get_package_depth(self, pkg_name: str) -> int:
        """Get the dependency depth of a package."""
        if pkg_name in self._graph:
            return self._graph[pkg_name].depth
        return -1

    def get_dependencies(self, pkg_name: str) -> Set[str]:
        """Get direct dependencies of a package."""
        if pkg_name in self._graph:
            return set(self._graph[pkg_name].dependencies)
        return set()

    def get_dependents(self, pkg_name: str) -> Set[str]:
        """Get packages that depend on this package."""
        if pkg_name in self._graph:
            return set(self._graph[pkg_name].dependents)
        return set()

    def is_dependency_of(self, pkg: str, potential_dep: str) -> bool:
        """Check if potential_dep is a dependency of pkg."""
        all_deps = self._collect_all_dependencies(pkg)
        return potential_dep in all_deps

    @property
    def errors(self) -> List[str]:
        """Get dependency resolution errors."""
        return self._errors

    @property
    def graph(self) -> Dict[str, DependencyNode]:
        """Get the dependency graph."""
        return self._graph


class DependencyError(Exception):
    """Exception raised for dependency resolution errors."""
    pass
