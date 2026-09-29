# Shared test helpers: paths to the fixture repos and a quick way to analyze one source snippet.
from __future__ import annotations

from pathlib import Path

import pytest

from repotour.analyzers import analyze_file
from repotour.analyzers.base import Context, FileFacts

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def py_app() -> Path:
    return FIXTURES / "py_app"


@pytest.fixture
def ts_app() -> Path:
    return FIXTURES / "ts_app"


@pytest.fixture
def mixed() -> Path:
    return FIXTURES / "mixed"


@pytest.fixture
def min_template() -> Path:
    return FIXTURES / "min_template.html"


def analyze_snippet(path: str, text: str, other_files: tuple[str, ...] = ()) -> FileFacts:
    """Run the analyzer for `path` on `text`, pretending the repo also holds `other_files`."""
    ctx = Context(root=Path("."), files=frozenset({path, *other_files}))
    return analyze_file(path, text, ctx)
