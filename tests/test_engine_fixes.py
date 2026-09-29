# Regression tests for engine fixes: literal glob-character paths, skip dirs in and out of git,
# render/install failures, notes coverage warnings and empty-field warnings.
import subprocess

import pytest

from repotour.build import build_data
from repotour.cli import main
from repotour.render import RenderError, write_html
from repotour.scan import scan_files


def write(root, rel, text="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def tour(root, body):
    write(root, ".repotour/tour.yaml", body)


# 1. literal names with glob characters


def test_literal_file_names_with_glob_characters(tmp_path):
    write(tmp_path, "pages/[id].tsx", "export const A = 1;\n")
    write(tmp_path, "app/[...slug]/page.tsx", "export const B = 1;\n")
    tour(
        tmp_path,
        "parts:\n  - {id: p, name: P, summary: s}\n"
        "problems:\n  - id: P1\n    part: p\n    title: t\n    fix: f\n"
        "    files: ['pages/[id].tsx', 'app/[...slug]/page.tsx']\n",
    )
    write(tmp_path, ".repotour/notes.yaml", "{}")
    data = build_data(tmp_path)
    assert set(data["problems"][0]["files"]) == {"pages/[id].tsx", "app/[...slug]/page.tsx"}
    assert not any("matches no file" in w or "not listed" in w for w in data["warnings"])


# 2. skip dirs


def test_git_repo_trusts_git_for_build_dirs(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel in ("build/a.py", "src/vendor/b.py", "env/c.py", "node_modules/d.js", "keep.py", "x_cache/e.py"):
        write(tmp_path, rel)
    assert scan_files(tmp_path).files == ["build/a.py", "env/c.py", "keep.py", "src/vendor/b.py"]


def test_non_git_skips_full_list_at_any_depth(tmp_path):
    rels = ("build/a.py", "src/vendor/b.py", "pkg/env/c.py", "pkg/coverage/d.py", "x_cache/e.py", "keep.py")
    for rel in rels:
        write(tmp_path, rel)
    assert scan_files(tmp_path).files == ["keep.py"]


# 4. render


def test_write_html_creates_parent_dirs(tmp_path, min_template):
    out = tmp_path / "a" / "b" / "tour.html"
    write_html({"project": {"name": "x"}}, out, min_template)
    assert out.is_file()


def test_write_html_unwritable_raises_render_error(tmp_path, min_template):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(RenderError):
        write_html({}, blocker / "sub" / "tour.html", min_template)


def test_build_unwritable_out_exits_2_one_line(tmp_path, min_template, capsys):
    write(tmp_path, "a.py")
    blocker = tmp_path / "file"
    blocker.write_text("x")
    argv = ["build", str(tmp_path), "--out", str(blocker / "t.html"), "--template", str(min_template)]
    assert main(argv) == 2
    assert capsys.readouterr().err.count("\n") == 1


# 5. install-skill


def test_install_skill_refuses_then_forces(tmp_path, capsys):
    assert main(["install-skill", "--project", str(tmp_path)]) == 0
    marker = tmp_path / ".claude" / "skills" / "repotour" / "marker.txt"
    marker.write_text("mine")
    assert main(["install-skill", "--project", str(tmp_path)]) == 2
    assert "--force" in capsys.readouterr().err and marker.exists()
    assert main(["install-skill", "--project", str(tmp_path), "--force"]) == 0
    assert not marker.exists()


def test_install_skill_force_replaces_symlink_not_its_target(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "keep.txt").write_text("keep")
    target = tmp_path / ".claude" / "skills" / "repotour"
    target.parent.mkdir(parents=True)
    target.symlink_to(real, target_is_directory=True)
    assert main(["install-skill", "--project", str(tmp_path), "--force"]) == 0
    assert not target.is_symlink() and (target / "SKILL.md").is_file()
    assert (real / "keep.txt").read_text() == "keep"


# 6. notes coverage


def _notes_repo(tmp_path):
    write(tmp_path, "src/a.py", "def one():\n    return 1\n\n\ndef two():\n    return 2\n")
    write(tmp_path, "tests/test_a.py", "def test_a():\n    pass\n")
    tour(
        tmp_path,
        "parts:\n  - {id: p, name: P, summary: s}\n"
        "problems:\n  - {id: P1, part: p, title: t, fix: f, files: [src/a.py], tests: [tests/test_a.py]}\n",
    )


def test_notes_coverage_warning_skips_tests(tmp_path):
    _notes_repo(tmp_path)
    warnings = build_data(tmp_path)["warnings"]
    assert "notes.yaml: no notes for src/a.py (2 items)" in warnings
    assert not any("test_a" in w for w in warnings)


def test_notes_coverage_silent_when_file_has_entry_and_in_auto_mode(tmp_path):
    _notes_repo(tmp_path)
    notes = "src/a.py: {_file: Two functions., one: Returns 1., two: Returns 2.}\n"
    write(tmp_path, ".repotour/notes.yaml", notes)
    assert build_data(tmp_path)["warnings"] == []
    (tmp_path / ".repotour" / "tour.yaml").unlink()
    (tmp_path / ".repotour" / "notes.yaml").unlink()
    assert build_data(tmp_path)["warnings"] == []


def test_missing_purpose_warns_for_non_test_files_only(tmp_path):
    _notes_repo(tmp_path)
    msg = "src/a.py: no purpose line (add _file in notes.yaml or a header comment)"
    assert msg in build_data(tmp_path)["warnings"]
    write(
        tmp_path,
        ".repotour/notes.yaml",
        "src/a.py: {_file: Two functions., one: Returns 1., two: Returns 2.}\n",
    )
    assert build_data(tmp_path)["warnings"] == []
    write(tmp_path, "src/a.py", '"""Two functions."""\n\n\ndef one():\n    return 1\n')
    (tmp_path / ".repotour" / "notes.yaml").unlink()
    assert msg not in build_data(tmp_path)["warnings"]


# 7. required vs recommended fields


def test_empty_recommended_fields_warn(tmp_path):
    write(tmp_path, "a.py", '"""A."""\n')
    tour(
        tmp_path,
        "parts:\n  - {id: p}\nproblems:\n  - {id: P1, part: p, files: [a.py]}\nstories:\n  - {id: S1}\n",
    )
    warnings = build_data(tmp_path)["warnings"]
    for text in (
        "part 'p': name is empty",
        "part 'p': summary is empty",
        "problem 'P1': title is empty",
        "problem 'P1': fix is empty",
        "story 'S1': title is empty",
        "story 'S1': steps is empty",
    ):
        assert f"tour.yaml: {text}" in warnings
