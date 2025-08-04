from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from tomlkit import TOMLDocument, items

from pdm import termui
from pdm.exceptions import ProjectError
from pdm.project.toml_file import TOMLBase
from pdm.utils import normalize_name


def _remove_empty_tables(doc: dict) -> None:
    for k, v in list(doc.items()):
        if isinstance(v, dict):
            _remove_empty_tables(v)
            if not v:
                del doc[k]


class PyProject(TOMLBase):
    """The data object representing th pyproject.toml file"""

    def read(self) -> TOMLDocument:
        from pdm.formats import flit, poetry

        data = super().read()
        if "project" not in data and self._path.exists():
            # Try converting from flit and poetry
            for converter in (flit, poetry):
                if converter.check_fingerprint(None, self._path):
                    metadata, settings = converter.convert(None, self._path, None)
                    data["project"] = metadata
                    if settings:
                        data.setdefault("tool", {}).setdefault("pdm", {}).update(settings)
                    break
        return data

    def write(self, show_message: bool = True) -> None:
        """Write the TOMLDocument to the file."""
        _remove_empty_tables(self._data.get("project", {}))
        _remove_empty_tables(self._data.get("tool", {}).get("pdm", {}))
        super().write()
        if show_message:
            self.ui.echo("Changes are written to [success]pyproject.toml[/].", verbosity=termui.Verbosity.NORMAL)

    @property
    def is_valid(self) -> bool:
        return bool(self._data.get("project"))

    @property
    def metadata(self) -> items.Table:
        return self._data.setdefault("project", {})

    @property
    def dependency_groups(self) -> items.Table:
        """Get dependency groups from PEP 735 [dependency-groups] table.

        This property specifically returns the PEP 735 format dependency groups.
        For backward compatibility with legacy format, use dev_dependencies property.
        """
        from tomlkit.container import Container

        base_table = self._data.setdefault("dependency-groups", {})

        # Override item() method to create missing keys automatically
        if hasattr(base_table, 'item'):
            original_item = base_table.item

            def safe_item(key):
                try:
                    return original_item(key)
                except Exception:
                    # Create empty array for missing key
                    import tomlkit
                    empty_array = tomlkit.array()
                    base_table[key] = empty_array
                    return base_table.item(key)

            base_table.item = safe_item

        return base_table

    def get_dependency_group_safe(self, group_name: str) -> list:
        """Safely get a dependency group from any location (PEP 735, legacy, or optional-dependencies).

        This method checks all possible locations for a dependency group and returns
        the dependencies as a list. Returns empty list if group doesn't exist.
        """
        # Check optional-dependencies first (highest priority)
        optional_deps = self.metadata.get("optional-dependencies", {})
        if group_name in optional_deps:
            deps = optional_deps[group_name]
            return deps.unwrap() if hasattr(deps, "unwrap") else deps

        # Check legacy dev-dependencies
        legacy_deps = self.settings.get("dev-dependencies", {})
        if group_name in legacy_deps:
            deps = legacy_deps[group_name]
            return deps.unwrap() if hasattr(deps, "unwrap") else deps

        # Check PEP 735 dependency-groups
        pep735_groups = self._data.get("dependency-groups", {})
        if group_name in pep735_groups:
            deps = pep735_groups[group_name]
            return deps.unwrap() if hasattr(deps, "unwrap") else deps

        # Return empty list if group doesn't exist anywhere
        return []

    @property
    def dev_dependencies(self) -> dict[str, list[Any]]:
        """Get all development dependency groups from both PEP 735 and legacy formats.

        This merges groups from both [dependency-groups] and [tool.pdm.dev-dependencies].
        If a group exists in both places, the legacy format takes precedence for --dev operations.
        """
        groups: dict[str, list[Any]] = {}

        # First, add groups from the legacy format (tool.pdm.dev-dependencies)
        legacy_dev_dependencies = self.settings.get("dev-dependencies", {})
        for group, deps in legacy_dev_dependencies.items():
            group = normalize_name(group)
            # Ensure deps is a list and handle both dict and list entries
            dep_list = deps.unwrap() if hasattr(deps, "unwrap") else deps
            if isinstance(dep_list, list):
                groups.setdefault(group, []).extend(dep_list)
            else:
                groups.setdefault(group, []).append(dep_list)

        # Then, add groups from PEP 735 format (dependency-groups) that don't exist in legacy
        pep735_groups = self._data.get("dependency-groups", {})
        for group, deps in pep735_groups.items():
            group = normalize_name(group)
            # Only add if not already in legacy dev-dependencies
            if group not in groups:
                dep_list = deps.unwrap() if hasattr(deps, "unwrap") else deps
                if isinstance(dep_list, list):
                    # Validate include-group references for PEP 735 groups
                    for dep in dep_list:
                        if isinstance(dep, dict) and "include-group" in dep:
                            included_group = dep["include-group"]
                            # Check if the included group exists in available groups
                            all_available_groups = set(legacy_dev_dependencies.keys())
                            all_available_groups.update(self.metadata.get("optional-dependencies", {}).keys())
                            # Don't include groups from dependency-groups in the validation
                            # since we're still building that list
                            if included_group not in all_available_groups:
                                from pdm.exceptions import PdmUsageError
                                raise PdmUsageError(f"Dependency group '{included_group}' not found")
                    groups[group] = dep_list
                else:
                    groups[group] = [dep_list]

        return groups

    @property
    def settings(self) -> items.Table:
        return self._data.setdefault("tool", {}).setdefault("pdm", {})

    @property
    def build_system(self) -> dict:
        return self._data.get("build-system", {})

    @property
    def resolution(self) -> Mapping[str, Any]:
        """A compatible getter method for the resolution overrides
        in the pyproject.toml file.
        """
        return self.settings.get("resolution", {})

    @property
    def allow_prereleases(self) -> bool | None:
        return self.resolution.get("allow-prereleases")

    def content_hash(self, algo: str = "sha256") -> str:
        """Generate a hash of the sensible content of the pyproject.toml file.
        When the hash changes, it means the project needs to be relocked.
        """
        dump_data = {
            "sources": self.settings.get("source", []),
            "dependencies": self.metadata.get("dependencies", []),
            "dev-dependencies": self.dev_dependencies,
            "optional-dependencies": self.metadata.get("optional-dependencies", {}),
            "requires-python": self.metadata.get("requires-python", ""),
            "resolution": self.resolution,
        }
        pyproject_content = json.dumps(dump_data, sort_keys=True)
        hasher = hashlib.new(algo)
        hasher.update(pyproject_content.encode("utf-8"))
        return hasher.hexdigest()

    @property
    def plugins(self) -> list[str]:
        return self.settings.get("plugins", [])
