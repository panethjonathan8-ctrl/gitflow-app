#!/usr/bin/env python3
"""Updates image.tag in a Helm values file."""
import re
import sys


def update_image_tag(values_file: str, tag: str) -> None:
    with open(values_file, "r") as f:
        content = f.read()

    updated = re.sub(r'(tag:\s*")[^"]*(")', rf"\g<1>{tag}\g<2>", content)

    if updated == content:
        print(f"WARNING: no tag field found in {values_file}", file=sys.stderr)
        sys.exit(1)

    with open(values_file, "w") as f:
        f.write(updated)

    print(f"Updated image tag to {tag} in {values_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <values-file> <tag>", file=sys.stderr)
        sys.exit(1)
    update_image_tag(sys.argv[1], sys.argv[2])
