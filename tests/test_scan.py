# Tests for file discovery (skips, suffixes, include/exclude, size limit) and for speed.
import subprocess
import time

from repotour.build import build_data
from repotour.scan import scan_files


def write(root, rel, text="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_default_skips_and_suffixes(tmp_path):
    for rel in (
        "a.py",
        "b.ts",
        "notes.md",
        "package-lock.json",
        "app.min.js",
        "x.map",
        "node_modules/m/i.js",
        "dist/o.js",
        ".venv/lib/x.py",
        "vendor/v.py",
        "__pycache__/c.py",
        "data.bin",
        "s.sh",
    ):
        write(tmp_path, rel)
    assert scan_files(tmp_path).files == ["a.py", "b.ts", "s.sh"]


def test_include_and_exclude(tmp_path):
    for rel in ("src/a.py", "src/b.py", "docs/guide.md", "gen/z.py"):
        write(tmp_path, rel)
    assert scan_files(tmp_path, exclude=["gen/**"]).files == ["src/a.py", "src/b.py"]
    assert scan_files(tmp_path, include=["docs/*.md", "src/a.py"]).files == ["docs/guide.md", "src/a.py"]


def test_large_files_are_skipped_with_warning(tmp_path):
    write(tmp_path, "big.py", "x = 1\n" * 200_000)
    write(tmp_path, "ok.py")
    result = scan_files(tmp_path)
    assert result.files == ["ok.py"]
    assert "big.py" in result.warnings[0]


def test_git_ignored_files_are_left_out(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, "keep.py")
    write(tmp_path, "secret.py")
    write(tmp_path, ".gitignore", "secret.py\n")
    assert scan_files(tmp_path).files == ["keep.py"]


def test_scan_include_exclude_come_from_tour_yaml(tmp_path):
    write(tmp_path, "a.py")
    write(tmp_path, "skip/b.py")
    write(tmp_path, ".repotour/tour.yaml", "scan:\n  exclude: ['skip/**']\n")
    assert list(build_data(tmp_path)["files"]) == ["a.py"]


def test_three_thousand_files_build_quickly(tmp_path):
    body = "import os\nfrom .m0 import f\n\n\ndef _h():\n    return 1\n\n\ndef f(x):\n    return _h() + x\n"
    ts = "import { a } from './m0';\nexport function g(x) { return x + 1; }\n"
    for i in range(1500):
        write(tmp_path, f"pkg{i % 30}/m{i}.py", body)
        write(tmp_path, f"web{i % 30}/m{i}.ts", ts)
    start = time.time()
    data = build_data(tmp_path)
    elapsed = time.time() - start
    assert data["stats"]["files"] == 3000
    assert elapsed < 20, elapsed
