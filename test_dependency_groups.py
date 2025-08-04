#!/usr/bin/env python3
"""Test script to verify PEP 735 dependency groups implementation"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Repo/src'))

from pdm.project.project_file import PyProject
from pdm import termui
import tomlkit
from pathlib import Path
import tempfile

# Create a mock UI for testing
class MockUI:
    def echo(self, message, err=False, verbosity=None):
        print(f"UI: {message}")

def create_test_pyproject(content):
    """Create a temporary pyproject.toml file with the given content"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(content)
        return f.name

def test_pep735_format():
    """Test that PEP 735 format [dependency-groups] works correctly"""
    print("\n=== Testing PEP 735 format ===")

    content = """
[project]
name = "test-project"
version = "0.1.0"

[dependency-groups]
test = ["pytest>=7.0", "pytest-cov"]
doc = ["mkdocs", "mkdocs-material"]
"""

    path = create_test_pyproject(content)
    try:
        pyproject = PyProject(Path(path), ui=MockUI())
        pyproject._data = pyproject.read()

        # Test dependency_groups property
        groups = pyproject.dependency_groups()
        print(f"Dependency groups: {dict(groups)}")

        # Test dev_dependencies property
        dev_deps = pyproject.dev_dependencies
        print(f"Dev dependencies: {dev_deps}")

        # Verify the groups are correctly loaded
        assert "test" in dev_deps
        assert "doc" in dev_deps
        assert "pytest>=7.0" in dev_deps["test"]
        assert "mkdocs" in dev_deps["doc"]

        print("✓ PEP 735 format test passed!")

    finally:
        os.unlink(path)

def test_legacy_format():
    """Test that legacy format [tool.pdm.dev-dependencies] still works"""
    print("\n=== Testing legacy format ===")

    content = """
[project]
name = "test-project"
version = "0.1.0"

[tool.pdm.dev-dependencies]
test = ["pytest>=7.0", "pytest-cov"]
doc = ["mkdocs", "mkdocs-material"]
"""

    path = create_test_pyproject(content)
    try:
        pyproject = PyProject(Path(path), ui=MockUI())
        pyproject._data = pyproject.read()

        # Test dependency_groups property
        groups = pyproject.dependency_groups()
        print(f"Dependency groups: {dict(groups)}")

        # Test dev_dependencies property
        dev_deps = pyproject.dev_dependencies
        print(f"Dev dependencies: {dev_deps}")

        # Verify the groups are correctly loaded
        assert "test" in dev_deps
        assert "doc" in dev_deps
        assert "pytest>=7.0" in dev_deps["test"]
        assert "mkdocs" in dev_deps["doc"]

        print("✓ Legacy format test passed!")

    finally:
        os.unlink(path)

def test_both_formats():
    """Test behavior when both formats exist"""
    print("\n=== Testing both formats present ===")

    content = """
[project]
name = "test-project"
version = "0.1.0"

[dependency-groups]
test = ["pytest>=8.0"]
new-group = ["requests"]

[tool.pdm.dev-dependencies]
test = ["pytest>=7.0"]
doc = ["mkdocs"]
"""

    path = create_test_pyproject(content)
    try:
        pyproject = PyProject(Path(path), ui=MockUI())
        pyproject._data = pyproject.read()

        # Test dependency_groups property
        groups = pyproject.dependency_groups()
        print(f"Dependency groups returned: {dict(groups)}")

        # Test dev_dependencies property
        dev_deps = pyproject.dev_dependencies
        print(f"Dev dependencies merged: {dev_deps}")

        # Verify PEP 735 takes precedence for conflicting groups
        assert "pytest>=8.0" in dev_deps["test"], "PEP 735 should take precedence"
        assert "pytest>=7.0" not in dev_deps["test"], "Legacy version should not be included"

        # Verify non-conflicting groups are merged
        assert "new-group" in dev_deps
        assert "doc" in dev_deps
        assert "mkdocs" in dev_deps["doc"]

        print("✓ Both formats test passed!")

    finally:
        os.unlink(path)

def test_empty_initialization():
    """Test that new projects default to PEP 735 format"""
    print("\n=== Testing empty initialization ===")

    content = """
[project]
name = "test-project"
version = "0.1.0"
"""

    path = create_test_pyproject(content)
    try:
        pyproject = PyProject(Path(path), ui=MockUI())
        pyproject._data = pyproject.read()

        # Get dependency_groups - should initialize with PEP 735 format
        groups = pyproject.dependency_groups()

        # Add a new group
        groups["test"] = ["pytest"]

        # Check that it was added to the PEP 735 location
        assert "dependency-groups" in pyproject._data
        assert pyproject._data["dependency-groups"]["test"] == ["pytest"]
        assert "tool" not in pyproject._data or "pdm" not in pyproject._data.get("tool", {})

        print("✓ Empty initialization test passed!")

    finally:
        os.unlink(path)

if __name__ == "__main__":
    test_pep735_format()
    test_legacy_format()
    test_both_formats()
    test_empty_initialization()
    print("\n✅ All tests passed!")
