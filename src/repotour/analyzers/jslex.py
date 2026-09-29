# A small hand-written lexer for JavaScript/TypeScript. It does not build tokens; it only finds
# comments, strings, template literals and regex literals so they can be blanked out with spaces.
# Positions and line numbers stay the same, so regex matches on the cleaned text map straight back
# to the original text. String contents are remembered by the offset of their opening quote.
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN = re.compile(r"//|/\*|['\"`/]")
_SINGLE = re.compile(r"'(?:[^'\\\n]|\\[\s\S])*'?")
_DOUBLE = re.compile(r'"(?:[^"\\\n]|\\[\s\S])*"?')
_NOT_NEWLINE = re.compile(r"[^\n]")
_REGEX_AFTER_WORDS = frozenset(
    "return typeof case in of do else void throw delete new yield await instanceof".split()
)
_REGEX_AFTER_CHARS = frozenset("(,=:[!&|?{};+-*%<>~^}")
_WORD_BEFORE = re.compile(r"[A-Za-z_$][\w$]*$")


@dataclass
class Lexed:
    clean: str  # same length as the source; comments/strings/templates/regexes blanked
    strings: dict[int, str] = field(default_factory=dict)  # offset of opening quote -> content


def lex(text: str) -> Lexed:
    """Blank comments and literals in `text`, keeping newlines and offsets."""
    lexer = _Lexer(text)
    lexer.scan(0, nested=False)
    return Lexed(lexer.build(), lexer.strings)


class _Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.spans: list[tuple[int, int]] = []  # regions to blank
        self.strings: dict[int, str] = {}

    def build(self) -> str:
        pieces: list[str] = []
        pos = 0
        for start, end in self.spans:
            pieces.append(self.text[pos:start])
            pieces.append(_NOT_NEWLINE.sub(" ", self.text[start:end]))
            pos = end
        pieces.append(self.text[pos:])
        return "".join(pieces)

    def scan(self, i: int, nested: bool) -> int:
        """Scan code from i. At top level run to the end. Inside `${ }` stop after the matching `}`
        and return its index + 1. Only top-level findings are recorded."""
        text = self.text
        depth = 0
        while True:
            m = _TOKEN.search(text, i)
            if nested:
                stop = self._brace_end(i, m.start() if m else len(text), depth)
                if isinstance(stop, int):
                    return stop
                depth = stop[0]
            if m is None:
                return len(text)
            i = self._token(m.start(), m.group(), nested)

    def _brace_end(self, start: int, end: int, depth: int) -> int | tuple[int]:
        """Count braces in text[start:end]; return the index after the closing brace or the new depth."""
        for pos in range(start, end):
            ch = self.text[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    return pos + 1
                depth -= 1
        return (depth,)

    def _token(self, start: int, kind: str, nested: bool) -> int:
        text = self.text
        if kind == "//":
            end = text.find("\n", start)
            end = len(text) if end == -1 else end
            self._blank(start, end, nested)
            return end
        if kind == "/*":
            end = text.find("*/", start + 2)
            end = len(text) if end == -1 else end + 2
            self._blank(start, end, nested)
            return end
        if kind in "'\"":
            m = (_SINGLE if kind == "'" else _DOUBLE).match(text, start)
            end = m.end() if m else start + 1
            closed = end - start >= 2 and text[end - 1] == kind
            inner_end = end - 1 if closed else end
            self._blank(start + 1, inner_end, nested)
            if not nested:
                self.strings[start] = text[start + 1 : inner_end]
            return end
        if kind == "`":
            return self._template(start, nested)
        return self._slash(start, nested)

    def _template(self, start: int, nested: bool) -> int:
        text = self.text
        i = start + 1
        has_expression = False
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                i += 2
            elif ch == "`":
                break
            elif ch == "$" and text.startswith("${", i):
                has_expression = True
                i = self.scan(i + 2, nested=True)
            else:
                i += 1
        i = min(i, len(text))
        closed = i < len(text) and text[i] == "`"
        self._blank(start + 1, i, nested)
        if not nested and not has_expression:
            self.strings[start] = text[start + 1 : i]
        return i + 1 if closed else i

    def _slash(self, start: int, nested: bool) -> int:
        """A lone `/`: either division or the start of a regex literal."""
        if not self._regex_allowed(start):
            return start + 1
        text = self.text
        i = start + 1
        in_class = False
        while i < len(text) and text[i] != "\n":
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "[":
                in_class = True
            elif ch == "]":
                in_class = False
            elif ch == "/" and not in_class:
                self._blank(start + 1, i, nested)
                return i + 1
            i += 1
        return start + 1  # no closing slash on this line: not a regex

    def _regex_allowed(self, pos: int) -> bool:
        before = self.text[max(0, pos - 20) : pos].rstrip()
        if not before:
            return True
        if before[-1] in _REGEX_AFTER_CHARS:
            return True
        word = _WORD_BEFORE.search(before)
        return bool(word and word.group() in _REGEX_AFTER_WORDS)

    def _blank(self, start: int, end: int, nested: bool) -> None:
        if not nested and end > start:
            self.spans.append((start, end))
