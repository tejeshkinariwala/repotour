# Tests for the glob matcher: *, ?, **, [..] and {a,b} braces.
from repotour.globs import expand_braces, is_pattern, matches


def test_star_does_not_cross_folders():
    assert matches("src/a.py", "src/*.py")
    assert not matches("src/deep/a.py", "src/*.py")


def test_double_star_any_depth_including_none():
    assert matches("a.py", "**/a.py")
    assert matches("x/y/z/a.py", "**/a.py")
    assert matches("tests/a/b.py", "tests/**")


def test_pattern_without_slash_matches_file_name_anywhere():
    assert matches("deep/er/settings.yaml", "*.yaml")


def test_braces_and_classes():
    assert expand_braces("a.{js,ts}") == ["a.js", "a.ts"]
    assert matches("src/main.ts", "**/main.{py,js,ts}")
    assert matches("f1.py", "f[0-9].py")
    assert not matches("fa.py", "f[0-9].py")


def test_trailing_slash_means_everything_below():
    assert matches("src/api/x/y.py", "src/api/")


def test_case_insensitive_option():
    assert matches("Src/API/Client.PY", "**/*client*.py", ignore_case=True)
    assert not matches("Src/API/Client.PY", "**/*client*.py")


def test_is_pattern():
    assert is_pattern("a/*.py")
    assert not is_pattern("a/b.py")
