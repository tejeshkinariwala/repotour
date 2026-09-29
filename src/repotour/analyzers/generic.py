# Analyzer for every other text file (yaml, toml, json, shell, sql ...): language, line count and
# the header comment only. No outline.
from __future__ import annotations

from repotour.analyzers.base import Context, FileFacts, count_lines
from repotour.analyzers.headers import hash_comment_header, slash_comment_header

SLASH_COMMENT_LANGS = {"json", "javascript", "typescript"}
NO_HEADER_LANGS = {"json"}


class GenericAnalyzer:
    def analyze(self, path: str, text: str, ctx: Context) -> FileFacts:
        from repotour.analyzers import language_for

        lang = language_for(path)
        header = ""
        if lang == "sql":
            header = _sql_header(text)
        elif lang not in NO_HEADER_LANGS:
            header = hash_comment_header(text)
        return FileFacts(path=path, lang=lang, lines=count_lines(text), header=header)


def _sql_header(text: str) -> str:
    dashes = [line.strip()[2:].strip() for line in text.splitlines()[:5] if line.strip().startswith("--")]
    if dashes:
        return " ".join(part for part in dashes if part)[:300]
    return slash_comment_header(text)
