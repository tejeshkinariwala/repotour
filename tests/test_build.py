# Tests for the data model: exact key sets (SPEC section 4), auto mode, written mode and warnings.
import json

import pytest
from conftest import FIXTURES

from repotour.build import build_data
from repotour.config import ConfigError

TOP_KEYS = {"tool", "mode", "project", "built_at", "stats", "roles", "parts", "part_links", "problems",
            "stories", "guide", "files", "warnings"}  # fmt: skip
PART_KEYS = {"id", "name", "role", "summary", "folders", "color", "problems", "files", "lines"}
PROBLEM_KEYS = {"id", "part", "title", "without", "fix", "files", "tests", "placeholder"}
STORY_KEYS = {"id", "act", "title", "command", "summary", "steps"}
FILE_KEYS = {"lang", "lines", "purpose", "role", "problem", "part", "stories", "imports", "libs", "used_by"}
ITEM_KEYS = {"name", "kind", "line", "signature", "note", "exported", "methods", "calls", "children"}
METHOD_KEYS = {"name", "line", "signature", "note"}


def test_key_sets_written_mode(mixed):
    data = build_data(mixed)
    assert set(data) == TOP_KEYS
    assert data["mode"] == "written"
    assert set(data["tool"]) == {"name", "version", "url"}
    assert set(data["project"]) == {"name", "tagline", "overview", "repo_url", "branch"}
    assert set(data["stats"]) == {"files", "lines", "languages"}
    assert all(set(r) == {"id", "emoji", "name", "meaning"} for r in data["roles"])
    assert all(set(p) == PART_KEYS for p in data["parts"])
    assert all(set(p) == PROBLEM_KEYS for p in data["problems"])
    assert all(set(s) == STORY_KEYS for s in data["stories"])
    assert all(set(step) == {"text", "files"} for s in data["stories"] for step in s["steps"])
    assert all(set(g) == {"text", "story", "part"} for g in data["guide"])
    assert all(set(link) == {"from", "to", "imports"} for link in data["part_links"])
    for record in data["files"].values():
        assert set(record) - {"outline"} == FILE_KEYS
    outlined = data["files"]["src/core/engine.py"]
    assert set(outlined["outline"]) == {"items", "consts"}
    item = outlined["outline"]["items"][0]
    assert set(item) == ITEM_KEYS
    assert set(item["methods"][0]) == METHOD_KEYS
    assert "outline" not in data["files"]["config/settings.yaml"]
    json.dumps(data)  # must be serializable


def test_key_sets_auto_mode(py_app):
    data = build_data(py_app)
    assert set(data) == TOP_KEYS and data["mode"] == "auto"
    assert data["stories"] == [] and data["guide"] == []
    assert all(set(p) == PROBLEM_KEYS and p["placeholder"] for p in data["problems"])
    assert all(set(p) == PART_KEYS for p in data["parts"])


def test_built_at_has_local_offset_and_no_zone_name(py_app):
    assert __import__("re").fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d [+-]\d\d:\d\d", build_data(py_app)["built_at"]
    )


def test_auto_mode_parts_and_no_placement_warnings(py_app):
    data = build_data(py_app)
    assert [p["name"] for p in data["parts"]] == ["acme_app", "Tests"]
    assert not any("not listed" in w for w in data["warnings"])
    assert any("broken.py" in w for w in data["warnings"])  # only the syntax error
    assert len(data["warnings"]) == 1
    assert data["files"]["acme_app/models.py"]["part"] == "acme-app"
    assert data["files"]["tests/test_reports.py"]["problem"] == "tests-1"
    assert data["parts"][0]["id"] == "acme-app" and data["parts"][0]["folders"] == ["acme_app/"]


def test_auto_mode_looks_through_src(tmp_path):
    for rel in ("src/pkg/a.py", "src/pkg/b.py", "src/top.py", "docs/x.yaml", "root.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x = 1\n")
    names = [p["name"] for p in build_data(tmp_path)["parts"]]
    assert names == ["docs", "pkg", "Root"]


def test_written_mode_warnings_cover_every_kind(mixed):
    warnings = "\n".join(build_data(mixed)["warnings"])
    expected = [
        "'src/core/nothing_*.py': matches no file",
        "'src/core/missing.py': no such file",
        "listed under problems 'A1' and 'C3'",
        "not listed under any problem",
        "story 'S1' step 2: src/core/unlisted.py is not under any problem",
        "'src/nowhere/*.py': matches no file",
        "src/gone.py: file has notes but is not in the repo",
        "config/settings.yaml: file has notes but is not outlined",
        "missing note for '_parse'",
        "note for 'ghost' but no such item exists",
        "part 'empty' has no problems",
        "problem 'C2' has no files",
    ]
    for text in expected:
        assert text in warnings, text


def test_written_mode_placement_and_notes(mixed):
    data = build_data(mixed)
    assert data["files"]["src/app/routes.py"]["problem"] == "A1"  # first problem wins
    assert data["files"]["src/core/unlisted.py"]["problem"] == "unplaced-core"
    placeholder = next(p for p in data["problems"] if p["id"] == "unplaced-core")
    assert placeholder["placeholder"] and placeholder["files"] == ["src/core/unlisted.py"]
    server = data["files"]["src/app/server.py"]
    assert server["purpose"] == "Serves one request."  # _file note beats the docstring
    serve = next(i for i in server["outline"]["items"] if i["name"] == "serve")
    assert serve["note"].startswith("Cleans the text")
    assert serve["children"][0]["name"] == "_parse" and serve["children"][0]["note"] is None
    assert data["files"]["src/app/server.py"]["stories"] == ["S1"]
    assert data["guide"][0] == {"text": "Read the story first.", "story": "S1", "part": None}
    core_files = next(p for p in data["parts"] if p["id"] == "core")["files"]
    assert core_files == 3  # engine, test_engine, unlisted


def test_used_by_and_part_links(mixed):
    data = build_data(mixed)
    assert data["files"]["src/core/engine.py"]["used_by"] == ["src/app/server.py"]
    assert {"from": "app", "to": "core", "imports": 1} in data["part_links"]


@pytest.mark.parametrize(
    ("name", "needle"),
    [
        ("yaml_syntax", "tour.yaml: YAML syntax error"),
        ("notes_syntax", "notes.yaml: YAML syntax error"),
        ("unknown_part", "problems[0].part: unknown part 'nope'"),
        ("unknown_role", "role_rules[0].role: unknown role 'wizard'"),
        ("duplicate_part", "parts[1].id: duplicate part id 'a'"),
        ("duplicate_problem", "problems[1].id: duplicate problem id 'P1'"),
        ("duplicate_story", "stories[1].id: duplicate story id 'S1'"),
        ("guide_story", "guide[0].story: unknown story 'S9'"),
        ("guide_part", "guide[0].part: unknown part 'zzz'"),
    ],
)
def test_hard_errors_name_file_and_key(name, needle):
    with pytest.raises(ConfigError) as info:
        build_data(FIXTURES / "bad" / name)
    message = str(info.value)
    assert needle in message and "\n" not in message
    assert ".repotour/" in message
