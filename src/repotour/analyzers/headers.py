# Finds the "what is this file for" text at the top of a file: leading # comments or leading
# // and /* */ comment blocks. Analyzers use this when there is no docstring.
from __future__ import annotations

import re

from repotour.analyzers.base import one_line

_CODING = re.compile(r"^#.*coding[:=]")


def hash_comment_header(text: str) -> str:
    """Leading block of `#` comment lines, after a shebang or encoding line."""
    collected: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not collected and (not line or line.startswith("#!") or _CODING.match(line)):
            continue
        if not line.startswith("#"):
            break
        collected.append(line.lstrip("#").strip())
    return one_line(" ".join(part for part in collected if part))


_DIRECTIVE = re.compile(r"""^(['"])use [\w -]+\1\s*;?$""")
_NOISE_START = re.compile(
    r"^(?:eslint|prettier|jshint|jscs|istanbul|c8|global\b|globals\b|@ts-|@flow|@jsx|@license|@preserve|"
    r"@format|@refresh|@vitest|@jest|tslint|webpack|spdx-license|copyright\b|license\b|licensed\b|"
    r"\(c\)|\u00a9)",
    re.IGNORECASE,
)


def _is_noise(text: str) -> bool:
    """Tool directives and license banners: not a description of the file."""
    return bool(_NOISE_START.match(text.strip()))


def slash_comment_header(text: str) -> str:
    """Leading block of `//` lines or one `/* */` (or `/** */`) comment. Skips `///` directives,
    `'use strict'`-style directives, and tool or license comments before the real description."""
    lines = text.lstrip("\ufeff").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#!") or line.startswith("///") or _DIRECTIVE.match(line):
            i += 1
        elif line.startswith("/*"):
            end = _block_end(lines, i)
            if line.startswith("/*!") or _is_noise(_block_first_text(lines[i : end + 1])):
                i = end + 1
                continue
            return _block_comment(lines, i)
        elif line.startswith("//"):
            collected: list[str] = []
            while i < len(lines) and re.match(r"//(?!/)", lines[i].strip()):
                part = lines[i].strip().lstrip("/").strip()
                if not _is_noise(part):
                    collected.append(part)
                i += 1
            found = one_line(" ".join(part for part in collected if part))
            if found:
                return found
        else:
            break
    return ""


def _block_end(lines: list[str], start: int) -> int:
    for j in range(start, len(lines)):
        if "*/" in lines[j][2:] if j == start else "*/" in lines[j]:
            return j
    return len(lines) - 1


def _block_first_text(block: list[str]) -> str:
    for line in block:
        piece = re.sub(r"^/\*+|\*/.*$", "", line.strip()).strip()
        piece = re.sub(r"^\*+\s?", "", piece).strip()
        if piece:
            return piece
    return ""


def _block_comment(lines: list[str], start: int) -> str:
    body: list[str] = []
    for line in lines[start:]:
        done = "*/" in line
        piece = line.split("*/")[0] if done else line
        piece = piece.strip()
        piece = re.sub(r"^/\*+", "", piece).strip()
        piece = re.sub(r"^\*+\s?", "", piece).strip()
        if piece and not piece.startswith("@"):
            body.append(piece)
        if done:
            break
    return one_line(" ".join(body))
