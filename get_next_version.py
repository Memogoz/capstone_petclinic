# filename: get_next_version.py

import semver
import subprocess
import re

# Get the latest tag
result = subprocess.run(["git", "tag"], stdout=subprocess.PIPE, text=True)
tags = result.stdout.strip().split("\n")

# Filter semver-compatible tags (e.g., v1.2.3)
version_tags = [tag for tag in tags if re.match(r"^v\d+\.\d+\.\d+$", tag)]

if not version_tags:
    latest = "v0.0.0"
else:
    latest = sorted(version_tags, key=lambda s: semver.VersionInfo.parse(s[1:]))[-1]

# Remove 'v' prefix and parse
current_version = semver.VersionInfo.parse(latest.lstrip("v"))

# Bump the minor version (you can also bump major or patch)
next_version = current_version.bump_patch()

# Print new version with 'v' prefix
print(f"v{next_version}")
