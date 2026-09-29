# Template checks that run the page's JavaScript helpers under node.
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).parent.parent / "src" / "repotour" / "templates" / "tour.html"
NODE = shutil.which("node") or ("/opt/homebrew/bin/node" if Path("/opt/homebrew/bin/node").exists() else None)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _pr(text):
    src = TEMPLATE.read_text()
    esc = re.search(r"function esc\(v\) \{.*?\n\}\n", src, re.S)
    pr = re.search(r"function pr\(v\) \{.*?\n\}\n", src, re.S)
    assert esc, "esc() helper missing"
    assert pr, "pr() helper missing"
    script = esc.group(0) + pr.group(0) + "process.stdout.write(pr(" + json.dumps(text) + "));"
    return subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout


def test_backticks_become_code():
    assert _pr("`create` calls `createImpl`") == "<code>create</code> calls <code>createImpl</code>"


def test_html_inside_backticks_is_escaped():
    out = _pr("Renders `<img onerror=x>` safely")
    assert "<img" not in out
    assert out == "Renders <code>&lt;img onerror=x&gt;</code> safely"


def test_spans_do_not_cross_lines_and_unmatched_stays_literal():
    assert _pr("a `b\nc` d") == "a `b\nc` d"
    assert _pr("one ` tick") == "one ` tick"
