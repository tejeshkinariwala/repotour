# Analyzer registry and the single source of truth for languages: which suffixes are known, what
# language each one is, and which analyzer reads it.
# To support a new language, write a class with an `analyze(path, text, ctx)` method that returns a
# FileFacts (see base.py), add its suffixes to LANGUAGES, and map them to it in REGISTRY below.
from __future__ import annotations

import posixpath

LANGUAGES = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".json": "json",
    ".ini": "ini", ".cfg": "ini", ".sql": "sql",
}  # fmt: skip

# Suffixes the scanner picks up by default.
DEFAULT_SUFFIXES = frozenset(LANGUAGES)


def language_for(path: str) -> str:
    suffix = posixpath.splitext(path)[1].lower()
    if suffix in LANGUAGES:
        return LANGUAGES[suffix]
    return suffix.lstrip(".") or "text"


from repotour.analyzers.base import Analyzer, Context, FileFacts  # noqa: E402
from repotour.analyzers.generic import GenericAnalyzer  # noqa: E402
from repotour.analyzers.javascript import JavaScriptAnalyzer  # noqa: E402
from repotour.analyzers.python import PythonAnalyzer  # noqa: E402

_PYTHON = PythonAnalyzer()
_JAVASCRIPT = JavaScriptAnalyzer()
_GENERIC = GenericAnalyzer()

REGISTRY: dict[str, Analyzer] = {
    **{suffix: _PYTHON for suffix, lang in LANGUAGES.items() if lang == "python"},
    **{suffix: _JAVASCRIPT for suffix, lang in LANGUAGES.items() if lang in ("javascript", "typescript")},
}


def analyzer_for(path: str) -> Analyzer:
    return REGISTRY.get(posixpath.splitext(path)[1].lower(), _GENERIC)


def analyze_file(path: str, text: str, ctx: Context) -> FileFacts:
    """Parse one file with the analyzer registered for its suffix."""
    return analyzer_for(path).analyze(path, text, ctx)


__all__ = [
    "DEFAULT_SUFFIXES",
    "LANGUAGES",
    "REGISTRY",
    "Analyzer",
    "Context",
    "FileFacts",
    "analyze_file",
    "analyzer_for",
    "language_for",
]
