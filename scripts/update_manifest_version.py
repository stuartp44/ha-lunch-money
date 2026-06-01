#!/usr/bin/env python3
"""Update the Home Assistant manifest version for a semantic release."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: update_manifest_version.py <version>", file=sys.stderr)
        return 1

    version = sys.argv[1]
    manifest_path = Path("custom_components/lunch_money/manifest.json")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest_path.write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())