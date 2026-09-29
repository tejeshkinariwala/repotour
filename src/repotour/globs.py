# Glob patterns used in tour.yaml and in role rules.
# Supports * ? [...] ** and {a,b} braces. A pattern with no "/" matches the file name at any depth.
# A pattern ending in "/" means "everything under that folder".
from __future__ import annotations

import re
from functools import lru_cache

GLOB_CHARS = set("*?[{")


def is_pattern(text: str) -> bool:
    """True if the text contains glob characters (so it is not a plain path)."""
    return any(ch in GLOB_CHARS for ch in text)


def expand_braces(pattern: str) -> list[str]:
    """Expand the first {a,b} group (recursively) into separate patterns."""
    start = pattern.find("{")
    if start == -1:
        return [pattern]
    depth = 0
    for i in range(start, len(pattern)):
        if pattern[i] == "{":
            depth += 1
        elif pattern[i] == "}":
            depth -= 1
            if depth == 0:
                return _expand_group(pattern, start, i)
    return [pattern]  # unbalanced brace: treat literally


def _expand_group(pattern: str, start: int, end: int) -> list[str]:
    parts = _split_top_level(pattern[start + 1 : end])
    prefix, suffix = pattern[:start], pattern[end + 1 :]
    result: list[str] = []
    for part in parts:
        result.extend(expand_braces(prefix + part + suffix))
    return result


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return parts


def _single_to_regex(pattern: str) -> str:
    """Translate one brace-free pattern to a regex source string."""
    if pattern.endswith("/"):
        pattern += "**"
    out = ""
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif ch == "*":
            out += "[^/]*"
            i += 1
        elif ch == "?":
            out += "[^/]"
            i += 1
        elif ch == "[":
            close = pattern.find("]", i + 2)
            if close == -1:
                out += re.escape(ch)
                i += 1
            else:
                body = pattern[i + 1 : close]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out += "[" + body.replace("\\", "\\\\") + "]"
                i = close + 1
        else:
            out += re.escape(ch)
            i += 1
    if "/" not in pattern:
        out = "(?:.*/)?" + out
    return out


@lru_cache(maxsize=4096)
def compile_glob(pattern: str, ignore_case: bool = False) -> re.Pattern[str]:
    """Compile a pattern (with braces) into one regex that matches a whole repo-relative path."""
    sources = [_single_to_regex(p) for p in expand_braces(pattern)]
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile("^(?:" + "|".join(sources) + ")$", flags)


def matches(path: str, pattern: str, ignore_case: bool = False) -> bool:
    return compile_glob(pattern, ignore_case).match(path) is not None


def matches_any(path: str, patterns: list[str], ignore_case: bool = False) -> bool:
    return any(matches(path, p, ignore_case) for p in patterns)
