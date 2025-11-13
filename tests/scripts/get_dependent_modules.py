#!/usr/bin/env python3
"""Build and cache module dependency graph from imports.

This script analyzes Python files in ccbt/ to extract import statements
and build a dependency graph. The graph is cached for performance.

Usage:
    python tests/scripts/get_dependent_modules.py  # Build and cache graph
    python tests/scripts/get_dependent_modules.py --print  # Print graph
"""

from __future__ import annotations

import ast
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Cache file location
CACHE_FILE = Path(__file__).parent.parent / ".dependency_cache.json"


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import statements."""

    def __init__(self, file_path: Path) -> None:
        """Initialize visitor with file path for context."""
        self.file_path = file_path
        self.imports: set[str] = set()
        self.normalized_file_path = self._normalize_path(file_path)

    def _normalize_path(self, path: Path) -> str:
        """Normalize file path to module path."""
        # Convert to relative path from repo root
        try:
            rel_path = path.relative_to(Path.cwd())
        except ValueError:
            # If not relative, use as-is
            rel_path = path

        # Convert to module path format
        path_str = str(rel_path).replace("\\", "/")
        if path_str.startswith("ccbt/"):
            # Remove .py extension and convert to module path
            module_path = path_str[:-3] if path_str.endswith(".py") else path_str
            return module_path.replace("/", ".")
        return path_str

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            if alias.name.startswith("ccbt."):
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from-import statements."""
        if node.module and node.module.startswith("ccbt."):
            self.imports.add(node.module)
        self.generic_visit(node)


def extract_imports(file_path: Path) -> set[str]:
    """Extract import statements from a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        Set of imported module names (only ccbt.* modules)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        visitor = ImportVisitor(file_path)
        visitor.visit(tree)
        return visitor.imports
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return set()


def build_dependency_graph(ccbt_dir: Path) -> dict[str, list[str]]:
    """Build dependency graph from ccbt/ directory.

    Args:
        ccbt_dir: Path to ccbt/ directory

    Returns:
        Dictionary mapping module paths to list of modules that depend on them
    """
    graph: dict[str, list[str]] = defaultdict(list)

    # Find all Python files in ccbt/
    for py_file in ccbt_dir.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test" in py_file.name.lower():
            continue

        # Normalize file path to module path
        try:
            rel_path = py_file.relative_to(ccbt_dir.parent)
            module_path = str(rel_path).replace("\\", "/")
            if module_path.endswith(".py"):
                module_path = module_path[:-3]
            module_path = module_path.replace("/", ".")
        except ValueError:
            continue

        # Extract imports
        imports = extract_imports(py_file)
        for imported_module in imports:
            # For each imported module, add this module as a dependent
            graph[imported_module].append(module_path)

    # Convert to regular dict and sort lists
    return {k: sorted(set(v)) for k, v in graph.items()}


def get_file_module_path(file_path: str) -> str:
    """Convert file path to module path.

    Args:
        file_path: File path (e.g., "ccbt/peer/peer.py")

    Returns:
        Module path (e.g., "ccbt.peer.peer")
    """
    normalized = file_path.replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".")


def get_dependent_modules(
    file_paths: list[str],
    graph: dict[str, list[str]] | None = None,
) -> set[str]:
    """Get all modules that depend on the given files.

    Args:
        file_paths: List of changed file paths
        graph: Dependency graph (if None, will load from cache or build)

    Returns:
        Set of module paths that depend on the changed files
    """
    if graph is None:
        graph = load_or_build_graph()

    dependents: set[str] = set()

    for file_path in file_paths:
        # Skip non-Python files and non-ccbt files
        if not file_path.endswith(".py") or not file_path.startswith("ccbt/"):
            continue

        module_path = get_file_module_path(file_path)

        # Find all modules that import this module
        if module_path in graph:
            dependents.update(graph[module_path])

        # Also check for transitive dependencies (modules that depend on dependents)
        # Use a simple approach: if A imports B, and B imports C, and C changes,
        # then A should also be tested
        visited = set()
        to_check = [module_path]
        while to_check:
            current = to_check.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in graph:
                for dependent in graph[current]:
                    if dependent not in visited:
                        dependents.add(dependent)
                        to_check.append(dependent)

    return dependents


def load_or_build_graph() -> dict[str, list[str]]:
    """Load dependency graph from cache or build it.

    Returns:
        Dependency graph dictionary
    """
    # Try to load from cache
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open() as f:
                cached = json.load(f)
                logger.info(f"Loaded dependency graph from cache ({len(cached)} entries)")
                return cached
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, rebuilding...")

    # Build graph
    repo_root = Path(__file__).parent.parent.parent
    ccbt_dir = repo_root / "ccbt"
    if not ccbt_dir.exists():
        logger.error(f"ccbt/ directory not found at {ccbt_dir}")
        return {}

    logger.info("Building dependency graph...")
    graph = build_dependency_graph(ccbt_dir)

    # Save to cache
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w") as f:
            json.dump(graph, f, indent=2)
        logger.info(f"Cached dependency graph ({len(graph)} entries)")
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")

    return graph


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Build and cache module dependency graph")
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the dependency graph",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the dependency graph (ignore cache)",
    )

    args = parser.parse_args()

    if args.rebuild and CACHE_FILE.exists():
        CACHE_FILE.unlink()
        logger.info("Removed cache file, rebuilding...")

    graph = load_or_build_graph()

    if args.print:
        print(json.dumps(graph, indent=2))
    else:
        logger.info(f"Dependency graph ready ({len(graph)} entries)")


if __name__ == "__main__":
    main()

