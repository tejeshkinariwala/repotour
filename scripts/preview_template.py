#!/usr/bin/env python3
"""Inject a data JSON file into the tour template to preview it.

Usage: python scripts/preview_template.py tests/fixtures/sample_data.json out.html
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MARKER = "/*REPOTOUR_DATA*/null"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    template = Path(__file__).resolve().parent.parent / "src" / "repotour" / "templates" / "tour.html"
    html = template.read_text(encoding="utf-8")
    if html.count(MARKER) != 1:
        print(f"template must contain {MARKER} exactly once", file=sys.stderr)
        return 1
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    Path(argv[2]).write_text(html.replace(MARKER, blob), encoding="utf-8")
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
