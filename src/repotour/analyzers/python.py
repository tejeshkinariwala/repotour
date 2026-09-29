# Python analyzer, built on the standard library `ast` module.
# Produces the outline (functions, classes with methods, function tables), the imports resolved
# to in-repo files, the outside libraries, and the header (docstring or leading comment).
from __future__ import annotations

import ast
import copy
import posixpath
import re

from repotour.analyzers.base import Context, FileFacts, Item, Method, add_import, count_lines, one_line
from repotour.analyzers.headers import hash_comment_header
from repotour.analyzers.outline import arrange

MAX_ANNOTATION = 40
CONST_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
_TRY_NODES = tuple(getattr(ast, name) for name in ("Try", "TryStar") if hasattr(ast, name))


class PythonAnalyzer:
    def analyze(self, path: str, text: str, ctx: Context) -> FileFacts:
        facts = FileFacts(path=path, lang="python", lines=count_lines(text))
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError) as err:
            facts.header = hash_comment_header(text)
            line = getattr(err, "lineno", None) or 1
            facts.warnings.append(f"{path}: Python syntax error at line {line}, listed without an outline")
            return facts
        facts.header = _docstring_header(tree) or hash_comment_header(text)
        facts.items, facts.consts = _outline(tree)
        libs: set[str] = set()
        _collect_imports(tree, path, ctx, facts.imports, libs)
        facts.imports.pop(path, None)
        facts.libs = sorted(libs)
        return facts


# ---------------------------------------------------------------- header


_UNDERLINE = re.compile(r"^\s*([~=\-^*#+])\1*\s*$")
_LICENSE_FIELD = re.compile(r"^\s*:(copyright|license|licence):", re.IGNORECASE)


def _docstring_header(tree: ast.Module) -> str:
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    for paragraph in re.split(r"\n\s*\n", "\n".join(_prose_lines(doc.splitlines()))):
        if paragraph.strip():
            return one_line(paragraph)
    return ""


def _prose_lines(lines: list[str]) -> list[str]:
    """Blank out reST title blocks, lines without letters (ASCII art) and copyright/license fields."""
    out = list(lines)
    for i, line in enumerate(lines):
        if _UNDERLINE.match(line) and line.strip():
            out[i] = ""
            if i > 0 and lines[i - 1].strip() and not _UNDERLINE.match(lines[i - 1]):
                out[i - 1] = ""  # the title above the underline
            if i > 1 and _UNDERLINE.match(lines[i - 2]) and lines[i - 2].strip():
                out[i - 2] = ""  # overline
        elif not re.search(r"[A-Za-z]", line) or _LICENSE_FIELD.match(line):
            out[i] = ""
    return out


# ---------------------------------------------------------------- outline


def _flatten(body: list[ast.stmt]) -> list[ast.stmt]:
    """Top-level statements, looking inside if/else/try/except blocks for conditional definitions."""
    found: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.If):
            found += _flatten(node.body) + _flatten(node.orelse)
        elif isinstance(node, _TRY_NODES):
            found += _flatten(node.body)
            for handler in node.handlers:
                found += _flatten(handler.body)
            found += _flatten(node.orelse) + _flatten(node.finalbody)
        else:
            found.append(node)
    return found


def _is_overload(node: ast.AST) -> bool:
    if not isinstance(node, FunctionNode):
        return False
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if (isinstance(target, ast.Name) and target.id == "overload") or (
            isinstance(target, ast.Attribute) and target.attr == "overload"
        ):
            return True
    return False


def _collapse(nodes: list[ast.stmt]) -> list[ast.stmt]:
    """One node per name (first occurrence wins). For functions, an overload group is shown by its
    implementation, or by its first definition when there is none."""
    groups: dict[str, list[ast.stmt]] = {}
    order: list[ast.stmt] = []
    for node in nodes:
        name = getattr(node, "name", None)
        if isinstance(node, FunctionNode | ast.ClassDef) and name:
            if name not in groups:
                order.append(node)
            groups.setdefault(name, []).append(node)
        else:
            order.append(node)
    result: list[ast.stmt] = []
    for node in order:
        group = groups.get(getattr(node, "name", None) or "")
        if group and isinstance(node, FunctionNode):
            node = next((n for n in group if not _is_overload(n)), group[0])
        result.append(node)
    return result


def _outline(tree: ast.Module) -> tuple[list[Item], list[str]]:
    exported_names = _dunder_all(tree)
    body = _collapse(_flatten(tree.body))
    func_names = {n.name for n in body if isinstance(n, FunctionNode)}
    items: list[Item] = []
    refs: dict[str, set[str]] = {}
    consts: list[str] = []
    seen: set[str] = set()
    for node in body:
        item = None
        if isinstance(node, FunctionNode):
            item = Item(node.name, "function", node.lineno, _signature(node.name, node.args), True)
        elif isinstance(node, ast.ClassDef):
            item = _class_item(node)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            name = _assigned_name(node)
            if name is None:
                continue
            value = node.value
            if isinstance(value, ast.Dict | ast.List | ast.Tuple | ast.Set) and (
                _names_in(value) & func_names
            ):
                item = Item(name, "table", node.lineno, f"{name} = {_container_hint(value)}", True)
            elif CONST_NAME.match(name) and not name.startswith("_"):
                consts.append(name)
        if item is None or item.name in seen:
            continue
        seen.add(item.name)
        item.exported = not item.name.startswith("_") and (
            exported_names is None or item.name in exported_names
        )
        items.append(item)
        refs[item.name] = _names_in(node)
    return arrange(items, refs), consts


def _class_item(node: ast.ClassDef) -> Item:
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    signature = f"class {node.name}({bases})" if bases else f"class {node.name}"
    item = Item(node.name, "class", node.lineno, signature, True)
    for child in _collapse(_flatten(node.body)):
        if isinstance(child, FunctionNode) and child.name not in {m.name for m in item.methods}:
            item.methods.append(Method(child.name, child.lineno, _signature(child.name, child.args)))
    return item


def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    if isinstance(node, ast.AnnAssign):
        target = node.target
    elif len(node.targets) == 1:
        target = node.targets[0]
    else:
        return None
    return target.id if isinstance(target, ast.Name) else None


def _container_hint(value: ast.expr) -> str:
    if isinstance(value, ast.Dict):
        return "{...}"
    if isinstance(value, ast.List):
        return "[...]"
    if isinstance(value, ast.Tuple):
        return "(...)"
    return "{...}"


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _dunder_all(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and _assigned_name(node) == "__all__":
            if isinstance(node.value, ast.List | ast.Tuple):
                return {
                    e.value
                    for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
    return None


def _signature(name: str, args: ast.arguments) -> str:
    args = copy.deepcopy(args)
    everything = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    everything += [a for a in (args.vararg, args.kwarg) if a is not None]
    for arg in everything:
        if arg.annotation is not None and len(ast.unparse(arg.annotation)) > MAX_ANNOTATION:
            arg.annotation = None
    return f"{name}({ast.unparse(args)})"


# ---------------------------------------------------------------- imports


def _collect_imports(
    tree: ast.Module, path: str, ctx: Context, imports: dict[str, list[str]], libs: set[str]
) -> None:
    own_dir = posixpath.dirname(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _handle_import(alias.name, own_dir, ctx, imports, libs)
        elif isinstance(node, ast.ImportFrom):
            _handle_from(node, own_dir, ctx, imports, libs)


def _handle_import(
    dotted: str, own_dir: str, ctx: Context, imports: dict[str, list[str]], libs: set[str]
) -> None:
    parts = dotted.split(".")
    for end in range(len(parts), 0, -1):
        found = _find_module(parts[:end], _absolute_roots(ctx, own_dir), ctx)
        if found is not None and found[0] is not None:
            add_import(imports, found[0], [])
            return
    if parts[0] != "__future__":
        libs.add(parts[0])


def _handle_from(
    node: ast.ImportFrom, own_dir: str, ctx: Context, imports: dict[str, list[str]], libs: set[str]
) -> None:
    module_parts = node.module.split(".") if node.module else []
    if node.level > 0:
        base = own_dir
        for _ in range(node.level - 1):
            base = posixpath.dirname(base)
        roots = [base]
    else:
        roots = _absolute_roots(ctx, own_dir)
        if node.module == "__future__":
            return
    found = _find_module(module_parts, roots, ctx)
    if found is None:
        if node.level == 0 and module_parts:
            libs.add(module_parts[0])
        return
    module_file, package_dir = found
    names = [alias.name for alias in node.names]
    plain: list[str] = []
    for name in names:
        submodule = _submodule_file(package_dir, name, ctx) if package_dir is not None else None
        if submodule is not None:
            add_import(imports, submodule, [])
        else:
            plain.append(name)
    if module_file is not None and (plain or not names):
        add_import(imports, module_file, plain)


def _absolute_roots(ctx: Context, own_dir: str) -> list[str]:
    roots = list(ctx.python_roots)
    if own_dir not in roots:
        roots.append(own_dir)  # script-style: `import sibling`
    return roots


def _join(root: str, rel: str) -> str:
    return f"{root}/{rel}" if root and rel else (root or rel)


def _find_module(parts: list[str], roots: list[str], ctx: Context) -> tuple[str | None, str | None] | None:
    """Return (module file or None, package folder or None) for a dotted module, or None."""
    rel = "/".join(parts)
    for root in roots:
        base = _join(root, rel)
        if not parts:
            init = _join(base, "__init__.py")
            if base in ctx.dirs:
                return (init if init in ctx.files else None), base
            continue
        if base + ".py" in ctx.files:
            return base + ".py", None
        if _join(base, "__init__.py") in ctx.files:
            return _join(base, "__init__.py"), base
        if base in ctx.dirs:
            return None, base  # folder without __init__.py (namespace package)
    return None


def _submodule_file(package_dir: str, name: str, ctx: Context) -> str | None:
    base = _join(package_dir, name)
    for candidate in (base + ".py", _join(base, "__init__.py")):
        if candidate in ctx.files:
            return candidate
    return None
