# Finds the top-level declarations of a JS/TS file (functions, classes, arrow functions, types,
# function tables, `export default` forms) using regexes on the cleaned text plus bracket matching.
# `clean` is the source with comments and literals blanked; `text` is the original (same offsets),
# used when a signature needs the real default values.
from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from repotour.analyzers.base import Item, Method, one_line
from repotour.analyzers.outline import arrange

IDENT = r"[A-Za-z_$][\w$]*"
CONST_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
BRACKETS = re.compile(r"[{}()\[\];]")
IDENT_RE = re.compile(r"(?<![\w$])" + IDENT)
MAX_SIGNATURE = 120

# Text that may sit between `=` and a function value: `async`, or a wrapper call such as React.memo(.
VALUE_PREFIX = re.compile(r"(?:[\w$.]+\(\s*)?(?:async\s+)?")
FUNCTION_KEYWORD = re.compile(r"function\b\s*\*?\s*(?:" + IDENT + r")?")
SINGLE_ARROW = re.compile(r"(?P<single>" + IDENT + r")\s*=>")
FUNCTION = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?P<default>default\s+)?(?:declare\s+)?(?:async\s+)?function\b\s*\*?\s*"
    r"(?P<name>" + IDENT + r")?",
    re.MULTILINE,
)
CLASS = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?P<default>default\s+)?(?:declare\s+)?(?:abstract\s+)?"
    r"(?P<kw>class)\b(?:\s+(?P<name>" + IDENT + r"))?",
    re.MULTILINE,
)
VARIABLE = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?:declare\s+)?(?P<kw>const|let|var)\s+(?P<name>" + IDENT + r")",
    re.MULTILINE,
)
TYPE_DECL = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?:declare\s+)?(?:const\s+)?(?P<kw>interface|type|enum)\s+"
    r"(?P<name>" + IDENT + r")",
    re.MULTILINE,
)
DEFAULT_ARROW = re.compile(
    r"^[ \t]*export\s+default\s+(?:async\s+)?(?:(?P<paren>\((?:[^()]|\([^()]*\))*\))\s*(?::[^=;{]*?)?=>"
    r"|(?P<single>" + IDENT + r")\s*=>)",
    re.MULTILINE,
)
DEFAULT_NAME = re.compile(r"^[ \t]*export\s+default\s+(?P<name>" + IDENT + r")\s*;?[ \t]*$", re.MULTILINE)
DEFAULT_OBJECT = re.compile(r"^[ \t]*export\s+default\s*(?P<open>[{\[])", re.MULTILINE)
EXPORT_LIST = re.compile(r"^[ \t]*export\s*(?:type\s+)?\{(?P<body>[^}]*)\}(?!\s*from\b)", re.MULTILINE)
CJS_LIST = re.compile(r"^[ \t]*module\.exports\s*=\s*\{(?P<body>[^}]*)\}", re.MULTILINE)
CJS_NAME = re.compile(r"^[ \t]*(?:module\.)?exports\.(?P<name>" + IDENT + r")\s*=", re.MULTILINE)
METHOD = re.compile(
    r"^[ \t]*(?P<mods>(?:(?:public|private|protected|static|readonly|abstract|override|async|declare|"
    r"accessor)\s+)*)"
    r"(?:(?P<acc>get|set)\s+)?\*?\s*(?P<name>#?" + IDENT + r")\s*(?=[<(])",
    re.MULTILINE,
)
PROPERTY = re.compile(
    r"^[ \t]*(?P<mods>(?:(?:public|private|protected|static|readonly|override|declare|accessor)\s+)*)"
    r"(?P<name>#?" + IDENT + r")\s*(?::[^=;\n]*)?=\s*",
    re.MULTILINE,
)
NOT_METHODS = frozenset({"if", "for", "while", "switch", "catch", "return", "function", "with"})


class Brackets:
    """Index of bracket positions: depth at a position, matching closers, statement ends."""

    def __init__(self, clean: str) -> None:
        self.positions: list[int] = []
        self.depths: list[int] = []  # depth after each bracket
        self.pairs: dict[int, int] = {}
        self.zero_ends: list[int] = []  # ends of top-level { } / [ ] groups and of `;` statements
        stack: list[int] = []
        depth = 0
        for m in BRACKETS.finditer(clean):
            ch, pos = m.group(), m.start()
            if ch in "{([":
                depth += 1
                stack.append(pos)
            elif ch in "})]":
                depth = max(depth - 1, 0)
                if stack:
                    self.pairs[stack.pop()] = pos
                if depth == 0 and ch != ")":
                    self.zero_ends.append(pos + 1)
            elif depth == 0:  # ';'
                self.zero_ends.append(pos)
            self.positions.append(pos)
            self.depths.append(depth)

    def depth_at(self, pos: int) -> int:
        index = bisect_left(self.positions, pos)
        return self.depths[index - 1] if index else 0

    def statement_end(self, start: int, limit: int) -> int:
        index = bisect_left(self.zero_ends, start + 1)
        end = self.zero_ends[index] if index < len(self.zero_ends) else limit
        return min(end, limit)


@dataclass
class _Decl:
    start: int
    item: Item
    opener: str = ""  # "{" or "[" for a const that may become a table (if it names functions)
    has_body: bool = True  # False for a body-less overload signature
    alias: str | None = None  # `export const a = b as T`: b, when it may name a function item
    candidate: bool = False  # a non-function const: kept only when it is exported
    keyword: str = "const"


class Outliner:
    def __init__(self, text: str, clean: str) -> None:
        self.text = text
        self.clean = clean
        self.brackets = Brackets(clean)
        self.newlines = [i for i, ch in enumerate(text) if ch == "\n"]
        self.exported_names: set[str] = set()

    def line_of(self, pos: int) -> int:
        return bisect_right(self.newlines, pos - 1) + 1 if pos > 0 else 1

    def top_level(self, regex: re.Pattern[str]) -> list[re.Match[str]]:
        return [m for m in regex.finditer(self.clean) if self.brackets.depth_at(m.start()) == 0]

    # ------------------------------------------------------------ scanning helpers

    def _skip_ws(self, pos: int) -> int:
        clean = self.clean
        while pos < len(clean) and clean[pos].isspace():
            pos += 1
        return pos

    def _skip_angle(self, pos: int) -> int | None:
        """Index after the `>` that closes the `<` at pos. Brackets inside are skipped as units and
        the `>` of `=>` does not count. None if it never closes (so it was not a generic list)."""
        clean, pairs = self.clean, self.brackets.pairs
        depth, i = 0, pos
        while i < len(clean):
            ch = clean[i]
            if ch in "([{":
                close = pairs.get(i)
                if close is None:
                    return None
                i = close + 1
                continue
            if ch == "<":
                depth += 1
            elif ch == ">" and clean[i - 1] != "=":
                depth -= 1
                if depth == 0:
                    return i + 1
            elif ch in ";)]}":
                return None
            i += 1
        return None

    def _callable_open(self, pos: int) -> tuple[str, int] | None:
        """After a name (or `function`): optional `<generics>` then `(`. Returns (generics, index of `(`)."""
        clean = self.clean
        i = self._skip_ws(pos)
        generics = ""
        if i < len(clean) and clean[i] == "<":
            end = self._skip_angle(i)
            if end is None:
                return None
            generics = self.text[i:end]
            i = self._skip_ws(end)
        if i < len(clean) and clean[i] == "(" and i in self.brackets.pairs:
            return generics, i
        return None

    def _skip_type(self, pos: int, stop_at_arrow: bool) -> int | None:
        """Skip a type starting at pos, over balanced brackets. With stop_at_arrow return the index of
        the `=>` that ends a return type; otherwise return the index of the `=` that ends a variable's
        type annotation. None if it does not end in what was expected."""
        clean, pairs = self.clean, self.brackets.pairs
        i = pos
        while i < len(clean):
            ch = clean[i]
            if ch in "([{":
                close = pairs.get(i)
                if close is None:
                    return None
                i = close + 1
                continue
            if ch == "<":
                end = self._skip_angle(i)
                if end is None:
                    return None
                i = end
                continue
            if ch == "=" and clean[i + 1 : i + 2] == ">":
                if stop_at_arrow:
                    return i
                i += 2
                continue
            if ch == "=" and not stop_at_arrow:
                return i
            if ch in "=;,)]}":
                return None
            i += 1
        return None

    def _function_value(self, pos: int) -> tuple[str, str] | None:
        """If a function value starts at pos (`(a) =>`, `x =>`, `async () =>`, `function (a) {`, or one
        wrapped in a call like React.memo( ), return (generics, parameter text)."""
        clean = self.clean
        i = VALUE_PREFIX.match(clean, pos).end()  # type: ignore[union-attr]
        keyword = FUNCTION_KEYWORD.match(clean, i)
        if keyword:
            opened = self._callable_open(keyword.end())
            return (opened[0], self._params(opened[1])) if opened else None
        single = SINGLE_ARROW.match(clean, i)
        if single:
            return "", single.group("single")
        opened = self._callable_open(i)
        if opened is None:
            return None
        j = self._skip_ws(self.brackets.pairs[opened[1]] + 1)
        if clean.startswith("=>", j):
            return opened[0], self._params(opened[1])
        if clean.startswith(":", j) and self._skip_type(j + 1, stop_at_arrow=True) is not None:
            return opened[0], self._params(opened[1])
        return None

    def _has_body(self, close_paren: int) -> bool:
        """After a function's parameter list: True if a `{` body follows, False for a signature that
        ends at `;` or at the end of the line (an overload)."""
        clean, pairs = self.clean, self.brackets.pairs
        i = close_paren + 1
        while i < len(clean):
            ch = clean[i]
            if ch == "{":
                return True
            if ch == ";":
                return False
            if ch in "([":
                close = pairs.get(i)
                if close is None:
                    return False
                i = close + 1
                continue
            if ch == "<":
                end = self._skip_angle(i)
                i = end if end is not None else i + 1
                continue
            if ch == "\n":
                before = clean[close_paren + 1 : i].rstrip()
                after = clean[i:].lstrip()
                continues = after[:1] in ("|", "&", "{", "?", ".", "=", "<", ">", ",", ")")
                if (before and before[-1] in "|&:(<=>,") or continues:
                    i += 1
                    continue
                if before or after[:1]:
                    return False
            if ch in "})":
                return False
            i += 1
        return False

    def _header_end(self, pos: int, stops: str) -> int:
        """Index of the first depth-0 character in `stops`, skipping `<...>`, `(...)` and `[...]`."""
        clean, pairs = self.clean, self.brackets.pairs
        i = pos
        while i < len(clean):
            ch = clean[i]
            if ch in stops:
                return i
            if ch in "([":
                i = pairs.get(i, i) + 1
                continue
            if ch == "<":
                end = self._skip_angle(i)
                if end is not None:
                    i = end
                    continue
            i += 1
        return len(clean)

    def _signature(self, name: str, generics: str, params: str) -> str:
        return _tidy_signature(name, generics, params)

    # ------------------------------------------------------------ public entry

    def build(self) -> tuple[list[Item], list[str]]:
        decls: list[_Decl] = []
        consts: list[str] = []
        self._functions(decls)
        self._classes(decls)
        self._variables(decls, consts)
        self._types(decls)
        self._defaults(decls)
        self._export_lists()
        decls.sort(key=lambda d: d.start)
        unique: dict[str, _Decl] = {}
        for decl in decls:  # repeated declarations: keep the first; overloads: keep the implementation
            name = decl.item.name
            first = unique.get(name)
            if first is None:
                unique[name] = decl
            elif first.item.kind == "function" and decl.item.kind == "function":
                exported = first.item.exported or decl.item.exported
                if not first.has_body and decl.has_body:
                    unique[name] = first = decl
                first.item.exported = exported
        return self._finish(sorted(unique.values(), key=lambda d: d.start), consts)

    # ------------------------------------------------------------ declarations

    def _functions(self, decls: list[_Decl]) -> None:
        for m in self.top_level(FUNCTION):
            name = m.group("name") or ("default" if m.group("default") else None)
            if name is None:
                continue
            opened = self._callable_open(m.end())
            if opened is None:
                continue
            generics, paren = opened
            signature = self._signature(name, generics, self._params(paren))
            exported = bool(m.group("export"))
            item = self._item(name, "function", m.start(), signature, exported)
            decls.append(_Decl(m.start(), item, has_body=self._has_body(self.brackets.pairs[paren])))

    def _classes(self, decls: list[_Decl]) -> None:
        for m in self.top_level(CLASS):
            name = m.group("name")
            if name in ("extends", "implements"):
                name = None
            name = name or ("default" if m.group("default") else None)
            if name is None:
                continue
            brace = self._header_end(m.end(), "{;")
            has_brace = brace < len(self.clean) and self.clean[brace] == "{"
            signature = _tidy_signature(self.text[m.start("kw") : brace])
            item = self._item(name, "class", m.start(), signature, bool(m.group("export")))
            if has_brace and brace in self.brackets.pairs:
                item.methods = self._methods(brace)
            decls.append(_Decl(m.start(), item))

    def _variables(self, decls: list[_Decl], consts: list[str]) -> None:
        for m in self.top_level(VARIABLE):
            name = m.group("name")
            exported = bool(m.group("export"))
            init = self._initializer(m.end())
            if init is None:
                continue
            if CONST_NAME.match(name):
                consts.append(name)
            value, alias = self._peel(init)
            if value:
                sig = self._signature(name, value[0], value[1])
                decls.append(_Decl(m.start(), self._item(name, "function", m.start(), sig, exported)))
                continue
            item = self._item(name, "value", m.start(), f"{m.group('kw')} {name}", exported)
            opener = self.clean[init] if self.clean[init] in "{[" else ""
            decls.append(_Decl(m.start(), item, opener, alias=alias, candidate=True, keyword=m.group("kw")))

    def _initializer(self, pos: int) -> int | None:
        """After a variable's name: skip an optional `: Type` and the `=`; return where the value starts."""
        clean = self.clean
        i = self._skip_ws(pos)
        if clean[i : i + 1] == "!":
            i = self._skip_ws(i + 1)
        if clean[i : i + 1] == ":":
            end = self._skip_type(i + 1, stop_at_arrow=False)
            if end is None or clean[end : end + 1] != "=":
                return None
            i = end
        if clean[i : i + 1] != "=" or clean[i + 1 : i + 2] in ("=", ">"):
            return None
        return self._skip_ws(i + 1)

    def _peel(self, pos: int) -> tuple[tuple[str, str] | None, str | None]:
        """Look at an initializer through wrapping parens and a trailing `as T` / `satisfies T`.
        Returns (function value or None, identifier it consists of or None)."""
        clean = self.clean
        value = self._function_value(pos)
        if value:
            return value, None
        if clean[pos : pos + 1] == "(" and pos in self.brackets.pairs:
            close = self.brackets.pairs[pos]
            if re.match(r"\s*(?:as\b|satisfies\b|[;)\n]|$)", clean[close + 1 :]):
                return self._peel(self._skip_ws(pos + 1))
        ident = re.compile(IDENT).match(clean, pos)
        if ident and re.match(r"[ \t]*(?:as\b|satisfies\b|[;)\n]|$)", clean[ident.end() :]):
            return None, ident.group()
        return None, None

    def _types(self, decls: list[_Decl]) -> None:
        for m in self.top_level(TYPE_DECL):
            end = self._header_end(m.end(), "{=;")
            signature = _tidy_signature(self.text[m.start("kw") : end])
            decls.append(
                _Decl(
                    m.start(),
                    self._item(m.group("name"), "type", m.start(), signature, bool(m.group("export"))),
                )
            )

    def _defaults(self, decls: list[_Decl]) -> None:
        for m in self.top_level(DEFAULT_ARROW):
            params = m.group("single") or self._inner(m.group("paren"), m.start("paren"))
            decls.append(
                _Decl(m.start(), self._item("default", "function", m.start(), f"default({params})", True))
            )
        for m in self.top_level(DEFAULT_OBJECT):
            item = self._item("default", "table", m.start(), "", True)
            decls.append(_Decl(m.start(), item, opener=m.group("open")))
        for m in DEFAULT_NAME.finditer(self.clean):
            if self.brackets.depth_at(m.start()) == 0:
                self.exported_names.add(m.group("name"))

    def _export_lists(self) -> None:
        for regex in (EXPORT_LIST, CJS_LIST):
            for m in self.top_level(regex):
                for part in m.group("body").split(","):
                    local = re.split(r"\s+as\s+|:", part.strip())[0].strip()
                    if local:
                        self.exported_names.add(re.sub(r"^type\s+", "", local))
        for m in self.top_level(CJS_NAME):
            self.exported_names.add(m.group("name"))

    # ------------------------------------------------------------ class members

    def _methods(self, open_brace: int) -> list[Method]:
        close = self.brackets.pairs[open_brace]
        found: dict[str, tuple[Method, bool]] = {}
        for m in METHOD.finditer(self.clean, open_brace + 1, close):
            name = m.group("name")
            if name in NOT_METHODS or self.brackets.depth_at(m.start()) != 1:
                continue
            opened = self._callable_open(m.end())
            if opened is None:
                continue
            generics, paren = opened
            prefix = "static " if "static" in m.group("mods") else ""
            prefix += f"{m.group('acc')} " if m.group("acc") else ""
            signature = self._signature(f"{prefix}{name}", generics, self._params(paren))
            has_body = self._has_body(self.brackets.pairs[paren])
            if name not in found or (not found[name][1] and has_body):  # overloads: keep the implementation
                found[name] = (Method(name, self.line_of(m.start()), signature), has_body)
        for m in PROPERTY.finditer(self.clean, open_brace + 1, close):
            name = m.group("name")
            if name in found or self.brackets.depth_at(m.start()) != 1:
                continue
            value = self._function_value(m.end())
            if value:
                prefix = "static " if "static" in m.group("mods") else ""
                signature = self._signature(f"{prefix}{name}", value[0], value[1])
                found[name] = (Method(name, self.line_of(m.start()), signature), True)
        return sorted((method for method, _ in found.values()), key=lambda method: method.line)

    # ------------------------------------------------------------ helpers

    def _item(self, name: str, kind: str, start: int, signature: str, exported: bool) -> Item:
        return Item(name, kind, self.line_of(start), signature, exported)

    def _params(self, open_paren: int) -> str:
        close = self.brackets.pairs.get(open_paren)
        if close is None:
            return ""
        return self.text[open_paren + 1 : close]

    def _inner(self, group: str, start: int) -> str:
        return one_line(self.text[start + 1 : start + len(group) - 1], MAX_SIGNATURE)

    def _finish(self, decls: list[_Decl], consts: list[str]) -> tuple[list[Item], list[str]]:
        limit = len(self.clean)
        extents: dict[str, str] = {}
        for index, decl in enumerate(decls):
            next_start = decls[index + 1].start if index + 1 < len(decls) else limit
            end = self.brackets.statement_end(decl.start, next_start)
            extents[decl.item.name] = self.clean[decl.start : end].replace("...", "   ")
        functions = {d.item.name: d.item for d in decls if d.item.kind == "function"}
        items: list[Item] = []
        refs: dict[str, set[str]] = {}
        for decl in decls:
            item = decl.item
            words = set(IDENT_RE.findall(extents[item.name]))
            item.exported = item.exported or item.name in self.exported_names
            if decl.candidate and not self._keep_candidate(decl, words, functions):
                continue
            if decl.opener:
                hint = "[...]" if decl.opener == "[" else "{...}"
                is_default = item.name == "default"
                if words & set(functions):
                    item.kind = "table"
                    item.signature = f"export default {hint}" if is_default else f"{item.name} = {hint}"
                elif is_default:
                    item.kind, item.signature = "const", f"export default {hint}"
                elif not decl.candidate:
                    continue
            items.append(item)
            refs[item.name] = words
        return arrange(items, refs), consts

    @staticmethod
    def _keep_candidate(decl: _Decl, words: set[str], functions: dict[str, Item]) -> bool:
        """Decide what a non-function const becomes: a `func` item if it is an alias of a top-level
        function, a table if it lists functions, a `value` item if exported, otherwise nothing."""
        item = decl.item
        if decl.opener and words & set(functions):
            return True  # becomes a table in _finish
        if not item.exported or CONST_NAME.match(item.name):
            return False
        target = functions.get(decl.alias or "")
        if target is not None and target.name != item.name:
            item.kind = "function"
            item.signature = item.name + target.signature[len(target.name) :]
        return True


def _tidy(text: str) -> str:
    """Drop newlines just inside brackets and a trailing comma before a closing bracket."""
    text = re.sub(r"([<(\[{])\s*\n\s*", r"\1", text.strip())
    return re.sub(r",?\s*\n\s*([>)\]}])", r"\1", text)


def _tidy_signature(head: str, generics: str = "", params: str | None = None) -> str:
    """One-line signature: `head<generics>(params)`, or just `head` when params is None. Whitespace
    is collapsed across lines and the result is cut at MAX_SIGNATURE characters."""
    if params is None:
        return one_line(_tidy(head), MAX_SIGNATURE)
    inner = re.sub(r",\s*$", "", _tidy(params))
    return one_line(f"{head}{_tidy(generics)}({inner})", MAX_SIGNATURE)
