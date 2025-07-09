"""
Pytest plugin that dynamically marks static tests based on their tag compatibility.

This plugin examines static test files and marks them as either:
- `tagged`: Tests that use the tag system (compatible)
- `untagged`: Tests that have hardcoded addresses (incompatible)
"""

import json
import re
from typing import Any, Dict

import pytest
import yaml

from pytest_plugins.filler.static_filler import NoIntResolver


def has_tags_in_content(content: Dict[str, Any]) -> bool:
    """Check if test content uses tags for addresses."""
    tag_pattern = re.compile(r"<(?:eoa|contract|coinbase)(?::[^:]+)?:[^>]+>")

    def check_dict(d: Dict[str, Any]) -> bool:
        """Recursively check dictionary for tags."""
        for _key, value in d.items():
            if isinstance(value, str) and tag_pattern.search(value):
                return True
            elif isinstance(value, dict):
                if check_dict(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and check_dict(item):
                        return True
                    elif isinstance(item, str) and tag_pattern.search(item):
                        return True
        return False

    return check_dict(content)


def pytest_collection_modifyitems(config, items):
    """Mark tests based on their tag usage."""
    # Only process if static tests are being filled
    if not config.getoption("fill_static_tests_enabled"):
        return

    # Track statistics
    tagged_count = 0
    untagged_count = 0

    # Group items by their source file
    items_by_file = {}
    for item in items:
        if hasattr(item, "parent") and hasattr(item.parent, "path"):
            file_path = item.parent.path
            if file_path not in items_by_file:
                items_by_file[file_path] = []
            items_by_file[file_path].append(item)

    # Process each file once
    for file_path, file_items in items_by_file.items():
        if file_path.suffix not in (".json", ".yml"):
            continue

        if not file_path.stem.endswith("Filler"):
            continue

        with open(file_path, "r") as f:
            file_content = (
                json.load(f) if file_path.suffix == ".json" else yaml.load(f, Loader=NoIntResolver)
            )

        # For each test in the file
        for test_name, test_content in file_content.items():
            # Check if the test uses tags
            uses_tags = has_tags_in_content(test_content)

            # Find items that belong to this test
            test_items = [item for item in file_items if test_name in item.name]

            # Mark items for this test
            for item in test_items:
                if uses_tags:
                    item.add_marker(pytest.mark.tagged)
                    tagged_count += 1
                else:
                    item.add_marker(pytest.mark.untagged)
                    untagged_count += 1

    # Report statistics if verbose
    if config.getoption("verbose") >= 1:
        print("\nStatic test tag statistics:")
        print(f"  Tagged (compatible): {tagged_count}")
        print(f"  Untagged (incompatible): {untagged_count}")


def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "tagged: marks tests that use the tag system")
    config.addinivalue_line("markers", "untagged: marks tests that have hardcoded addresses")
