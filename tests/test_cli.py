# Tests for the command line: exit codes, scan output, init, install-skill, build output.
import json
from pathlib import Path

import pytest
import yaml
from conftest import FIXTURES

from repotour import __version__
from repotour.cli import main
from repotour.render import PLACEHOLDER, render_html


def test_version(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_scan_json_entries(py_app, capsys):
    assert main(["scan", str(py_app), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    entry = next(f for f in data["files"] if f["path"] == "acme_app/models.py")
    assert set(entry) == {"path", "header", "lang", "lines", "role", "outline", "imports", "libs", "used_by"}
    assert entry["header"] == "Data shapes for orders."
    assert entry["outline"]["items"][0]["name"] == "Order"
    yaml_entry = next(f for f in data["files"] if f["path"] == "acme_app/settings.yaml")
    assert yaml_entry["outline"] is None


def test_scan_files_only(py_app, capsys):
    assert main(["scan", str(py_app), "--files-only"]) == 0
    lines = capsys.readouterr().out.split()
    assert "acme_app/models.py" in lines and "tests/test_reports.py" in lines
    assert main(["scan", str(py_app), "--files-only", "--json"]) == 0
    assert "acme_app/models.py" in json.loads(capsys.readouterr().out)


def test_scan_human_listing(ts_app, capsys):
    assert main(["scan", str(ts_app)]) == 0
    out = capsys.readouterr().out
    assert "src/lib/math.ts" in out and "add(a: number, b: number)" in out


def test_check_exit_codes(mixed, tmp_path, capsys):
    assert main(["check", str(mixed)]) == 1
    assert "warning:" in capsys.readouterr().err
    (tmp_path / "a.py").write_text('"""Clean."""\n')
    assert main(["check", str(tmp_path)]) == 0


def test_hard_error_exits_2_with_one_line(capsys):
    assert main(["check", str(FIXTURES / "bad" / "unknown_part")]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "tour.yaml" in err and "problems[0].part" in err


def test_missing_folder_exits_2(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope")]) == 2


def test_build_writes_html_and_strict(mixed, min_template, tmp_path, capsys):
    out = tmp_path / "tour.html"
    argv = ["build", str(mixed), "--out", str(out), "--template", str(min_template)]
    assert main(argv) == 0
    assert main([*argv, "--strict"]) == 1
    html = out.read_text()
    assert PLACEHOLDER not in html and "Acme Mixed" in html
    assert "Built" in capsys.readouterr().out


def test_build_default_output_path(min_template, tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert main(["build", str(tmp_path), "--template", str(min_template)]) == 0
    assert (tmp_path / ".repotour" / "tour.html").is_file()


def test_render_escapes_script_end():
    template = FIXTURES / "min_template.html"
    html = render_html({"project": {"name": "</script><b>"}}, template)
    assert "</script><b>" not in html and "\\u003c/script>" in html


def test_init_writes_starter_files_that_build(tmp_path, capsys):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        '"""Tiny module."""\n\n\ndef one():\n    return 1\n\n\nclass K:\n    def m(self): ...\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a(): ...\n")
    assert main(["init", str(tmp_path)]) == 0
    tour = yaml.safe_load((tmp_path / ".repotour" / "tour.yaml").read_text())
    notes = yaml.safe_load((tmp_path / ".repotour" / "notes.yaml").read_text())
    assert [p["id"] for p in tour["parts"]] == ["pkg", "tests"]
    assert notes["pkg/a.py"] == {"_file": "", "one": "", "K": "", "K.m": ""}
    assert main(["init", str(tmp_path)]) == 2  # refuses to overwrite
    assert main(["init", str(tmp_path), "--force"]) == 0
    assert main(["check", str(tmp_path)]) == 0  # starter files validate cleanly
    capsys.readouterr()


def test_install_skill_copies_package_skill(tmp_path, capsys):
    skill = Path(__file__).parent.parent / "src" / "repotour" / "skill" / "SKILL.md"
    code = main(["install-skill", "--project", str(tmp_path)])
    if not skill.is_file():
        assert code == 2 and "skill" in capsys.readouterr().err
        return
    assert code == 0
    assert (tmp_path / ".claude" / "skills" / "repotour" / "SKILL.md").is_file()


def test_install_skill_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert main(["install-skill", "--user"]) == 0
    assert (tmp_path / ".claude" / "skills" / "repotour" / "SKILL.md").is_file()
