#!/usr/bin/env python3
"""Parse CHANGELOG.md and extract the latest version and release notes."""

import os
import re
import sys


def parse_changelog(filepath="CHANGELOG.md"):
    """Extract the latest version and its content from CHANGELOG.md."""
    with open(filepath) as f:
        content = f.read()

    # Match version headers like ## [0.3.1] - 2026-02-10
    version_pattern = r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})"
    matches = list(re.finditer(version_pattern, content, re.MULTILINE))

    if not matches:
        print("Error: No version found in CHANGELOG.md", file=sys.stderr)
        sys.exit(1)

    # Get the first (latest) version
    first_match = matches[0]
    version = first_match.group(1)
    date = first_match.group(2)

    # Extract content between first and second version headers
    start_pos = first_match.end()
    if len(matches) > 1:
        end_pos = matches[1].start()
        body = content[start_pos:end_pos].strip()
    else:
        # If only one version, get everything after it until the end or separator
        remaining = content[start_pos:]
        separator_match = re.search(r"^---$", remaining, re.MULTILINE)
        if separator_match:
            body = remaining[: separator_match.start()].strip()
        else:
            body = remaining.strip()

    # Write release body to file for gh command
    with open("release_body.txt", "w") as f:
        f.write(body)

    # Write to GitHub Actions output
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"version={version}\n")
            f.write(f"tag=v{version}\n")

    print(f"Parsed version {version} (tag: v{version})")
    print(f"Release body: {len(body)} characters")


if __name__ == "__main__":
    parse_changelog()
