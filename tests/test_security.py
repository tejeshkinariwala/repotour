# Regression tests for untrusted repo content: symlinks pointing outside the repo, text that could
# break out of the page's script tag, and part colours that could inject CSS.
import json
import re

from repotour.build import build_data
from repotour.render import PLACEHOLDER, render_html
from repotour.scan import scan_files


def write(root, rel, text="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_symlinked_file_is_skipped_not_read(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("# secret host file\n")
    repo = tmp_path / "repo"
    write(repo, "app.py")
    (repo / "leak.py").symlink_to(outside)
    result = scan_files(repo)
    assert result.files == ["app.py"]
    assert any("leak.py" in w and "symbolic link" in w for w in result.warnings)


def test_script_breakout_text_is_escaped(tmp_path):
    template = tmp_path / "t.html"
    template.write_text(f"<script>const DATA = {PLACEHOLDER};</script>")
    data = {"note": "</script><!--<script>alert(1)"}
    html = render_html(data, template)
    body = html.split("const DATA = ", 1)[1].rsplit(";</script>", 1)[0]
    assert "<" not in body
    assert json.loads(body) == data


def test_part_color_rejects_css_injection(tmp_path):
    write(tmp_path, "a.py")
    write(
        tmp_path,
        ".repotour/tour.yaml",
        "parts:\n"
        "  - {id: good, name: G, summary: s, color: '#3b82f6'}\n"
        "  - {id: bad, name: B, summary: s, color: 'red;background:url(https://example.com/x)'}\n"
        "problems:\n  - {id: G1, part: good, title: t, fix: f, files: [a.py]}\n",
    )
    data = build_data(tmp_path)
    colors = {p["id"]: p["color"] for p in data["parts"]}
    assert colors["good"] == "#3b82f6"
    assert not colors["bad"] or not re.search(r"[;:()]", colors["bad"])
    assert any("part 'bad'" in w and "color" in w for w in data["warnings"])
