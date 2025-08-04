#!/usr/bin/env python3
"""Simple test to verify the logic of our changes"""

import tomlkit

# Mock the necessary components
class MockUI:
    def echo(self, message, err=False, verbosity=None):
        print(f"UI: {message}")

class items:
    class Table(dict):
        pass

# Simulate our modified dependency_groups method
def dependency_groups(data, settings, ui):
    """Simulated dependency_groups method logic"""
    # Check for new PEP 735 format: [dependency-groups]
    pep735_groups = data.get("dependency-groups", {})

    # Check for legacy format: [tool.pdm.dev-dependencies]
    legacy_groups = settings.get("dev-dependencies", {})

    # If both exist, warn the user and prefer the new format
    if pep735_groups and legacy_groups:
        ui.echo(
            "[warning]Both [dependency-groups] and [tool.pdm.dev-dependencies] "
            "tables exist. Using [dependency-groups] as per PEP 735.[/]",
            err=True
        )
        return pep735_groups

    # Use new format if it exists
    if pep735_groups:
        return pep735_groups

    # Otherwise fall back to legacy format
    if not legacy_groups and not pep735_groups:
        # When creating new groups, prefer PEP 735 format
        return data.setdefault("dependency-groups", {})

    return settings.setdefault("dev-dependencies", {})

# Test case 1: PEP 735 format only
print("=== Test 1: PEP 735 format only ===")
data1 = tomlkit.parse("""
[dependency-groups]
test = ["pytest>=7.0"]
doc = ["mkdocs"]
""")
settings1 = {}
ui1 = MockUI()
result1 = dependency_groups(data1, settings1, ui1)
print(f"Result: {dict(result1)}")
assert result1 == data1["dependency-groups"]
print("✓ Test 1 passed!\n")

# Test case 2: Legacy format only
print("=== Test 2: Legacy format only ===")
data2 = tomlkit.parse("""
[tool]
[tool.pdm]
""")
settings2 = {"dev-dependencies": {"test": ["pytest>=6.0"], "lint": ["flake8"]}}
ui2 = MockUI()
result2 = dependency_groups(data2, settings2, ui2)
print(f"Result: {dict(result2)}")
assert result2 == settings2["dev-dependencies"]
print("✓ Test 2 passed!\n")

# Test case 3: Both formats exist
print("=== Test 3: Both formats exist ===")
data3 = tomlkit.parse("""
[dependency-groups]
test = ["pytest>=8.0"]
new = ["requests"]
""")
settings3 = {"dev-dependencies": {"test": ["pytest>=6.0"], "old": ["legacy-pkg"]}}
ui3 = MockUI()
result3 = dependency_groups(data3, settings3, ui3)
print(f"Result: {dict(result3)}")
assert result3 == data3["dependency-groups"]
print("✓ Test 3 passed!\n")

# Test case 4: Empty initialization
print("=== Test 4: Empty initialization ===")
data4 = tomlkit.parse("""
[project]
name = "test"
""")
settings4 = {}
ui4 = MockUI()
result4 = dependency_groups(data4, settings4, ui4)
print(f"Result: {dict(result4)}")
assert "dependency-groups" in data4
print("✓ Test 4 passed!\n")

print("✅ All logic tests passed!")
