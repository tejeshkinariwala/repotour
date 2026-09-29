# Resolves JavaScript/TypeScript import specifiers to files in the repo.
# Handles relative paths (with extension guessing and index files), the TS habit of writing `.js`
# for a `.ts` file, and simple tsconfig.json / jsconfig.json `baseUrl` and `paths` aliases.
from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass, field

from repotour.analyzers.base import Context
from repotour.globs import matches_any

SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
JS_TO_TS = {".js": (".ts", ".tsx"), ".jsx": (".tsx", ".ts"), ".mjs": (".mts",), ".cjs": (".cts",)}
_JSON_COMMENTS = re.compile(r'("(?:[^"\\]|\\.)*")|//[^\n]*|/\*.*?\*/', re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


@dataclass
class TsConfig:
    folder: str  # folder that holds the config file
    base_dir: str  # folder that aliases are resolved against
    has_base_url: bool = False
    paths: list[tuple[str, list[str]]] = field(default_factory=list)  # longest prefix first
    include: list[str] = field(default_factory=list)  # repo-relative glob patterns; empty: everything
    exclude: list[str] = field(default_factory=list)

    def covers(self, path: str) -> bool:
        """True if the config's include/exclude patterns take in this file."""
        if self.include and not matches_any(path, self.include):
            return False
        return not (self.exclude and matches_any(path, self.exclude))


class JsResolver:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self._configs: dict[str, TsConfig | None] = {}

    def is_relative(self, spec: str) -> bool:
        return spec == "." or spec == ".." or spec.startswith(("./", "../"))

    def resolve(self, spec: str, from_dir: str, from_file: str | None = None) -> str | None:
        """Return the repo file a specifier points to, or None if it is not an in-repo file.
        Aliases come from the nearest tsconfig.json / jsconfig.json above the importing file."""
        if self.is_relative(spec):
            return self._try(_normalize(posixpath.join(from_dir, spec)))
        config = self._find_config(from_dir)
        if config is None or (from_file is not None and not config.covers(from_file)):
            return None
        for pattern, targets in config.paths:
            captured = _match_alias(pattern, spec)
            if captured is None:
                continue
            for target in targets:
                found = self._try(_normalize(posixpath.join(config.base_dir, target.replace("*", captured))))
                if found:
                    return found
        if config.has_base_url:
            return self._try(_normalize(posixpath.join(config.base_dir, spec)))
        return None

    def _try(self, path: str | None) -> str | None:
        if path is None:
            return None
        files = self.ctx.files
        if path in files:
            return path
        suffix = posixpath.splitext(path)[1]
        for alternative in JS_TO_TS.get(suffix, ()):
            if path[: -len(suffix)] + alternative in files:
                return path[: -len(suffix)] + alternative
        for extra in SUFFIXES:
            if path + extra in files:
                return path + extra
        for extra in SUFFIXES:
            candidate = f"{path}/index{extra}" if path else f"index{extra}"
            if candidate in files:
                return candidate
        return None

    def _find_config(self, from_dir: str) -> TsConfig | None:
        """The nearest config walking up from from_dir to the repo root (the first one that exists)."""
        if from_dir in self._configs:
            return self._configs[from_dir]
        found = self._load_config(from_dir)
        if found is None and from_dir:
            found = self._find_config(posixpath.dirname(from_dir))
        self._configs[from_dir] = found
        return found

    def _load_config(self, folder: str) -> TsConfig | None:
        for name in ("tsconfig.json", "jsconfig.json"):
            rel = posixpath.join(folder, name)
            if rel not in self.ctx.files:
                continue
            layers = self._layers(rel, followed=False)
            if layers is None:
                continue
            return _merge(folder, layers)
        return None

    def _layers(self, rel: str, followed: bool) -> list[tuple[str, dict]] | None:
        """[(folder, raw config)] from the extended config (one level) to this one."""
        text = self.ctx.read_repo_file(rel)
        data = _parse_json(text) if text else None
        if data is None:
            return None
        folder = posixpath.dirname(rel)
        layers: list[tuple[str, dict]] = []
        extends = data.get("extends")
        parents = [extends] if isinstance(extends, str) else extends if isinstance(extends, list) else []
        for parent in parents if not followed else []:
            if not isinstance(parent, str) or not parent.startswith("."):
                continue  # a package (e.g. @tsconfig/node20): not in the repo
            name = parent if parent.endswith(".json") else parent + ".json"
            target = _normalize(posixpath.join(folder, name))
            if target and target in self.ctx.files:
                layers += self._layers(target, followed=True) or []
        return [*layers, (folder, data)]


def _merge(folder: str, layers: list[tuple[str, dict]]) -> TsConfig:
    """Combine extended and own settings: later layers override earlier ones, key by key. `paths`
    resolve against baseUrl if there is one, otherwise against the folder of the file that set them."""
    base_dir: str | None = None
    paths: list[tuple[str, list[str]]] = []
    paths_dir = folder
    include: list[str] = []
    exclude: list[str] = []
    for layer_folder, data in layers:
        options = data.get("compilerOptions")
        options = options if isinstance(options, dict) else {}
        if isinstance(options.get("baseUrl"), str):
            base_dir = _normalize(posixpath.join(layer_folder, options["baseUrl"])) or ""
        if isinstance(options.get("paths"), dict):
            paths_dir = layer_folder
            paths = [
                (pattern, [t for t in targets if isinstance(t, str)])
                for pattern, targets in options["paths"].items()
                if isinstance(targets, list)
            ]
        for key, target in (("include", include), ("exclude", exclude)):
            if isinstance(data.get(key), list):
                target[:] = [_glob_from(layer_folder, p) for p in data[key] if isinstance(p, str)]
    paths.sort(key=lambda entry: -len(entry[0].split("*")[0]))
    return TsConfig(
        folder,
        base_dir if base_dir is not None else paths_dir,
        has_base_url=base_dir is not None,
        paths=paths,
        include=include,
        exclude=exclude,
    )


def _glob_from(folder: str, pattern: str) -> str:
    """A tsconfig include/exclude entry as a repo-relative glob. A name with no wildcard or
    extension is a folder and takes everything under it."""
    pattern = pattern.removeprefix("./")
    last = pattern.rsplit("/", 1)[-1]
    if pattern.endswith("/**"):
        pattern += "/*"
    elif "*" not in last and "." not in last:
        pattern = f"{pattern.rstrip('/')}/**/*"
    return posixpath.join(folder, pattern) if folder else pattern


def _parse_json(text: str) -> dict | None:
    cleaned = _JSON_COMMENTS.sub(lambda m: m.group(1) or "", text)
    cleaned = _TRAILING_COMMA.sub(r"\1", cleaned)
    try:
        data = json.loads(cleaned)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _normalize(path: str) -> str | None:
    normal = posixpath.normpath(path)
    if normal == ".":
        return ""
    if normal.startswith(".."):
        return None
    return normal


def _match_alias(pattern: str, spec: str) -> str | None:
    """Return the text matched by `*` (empty for exact patterns), or None if no match."""
    if "*" not in pattern:
        return "" if pattern == spec else None
    prefix, suffix = pattern.split("*", 1)
    if spec.startswith(prefix) and spec.endswith(suffix) and len(spec) >= len(prefix) + len(suffix):
        return spec[len(prefix) : len(spec) - len(suffix)]
    return None


def library_name(spec: str) -> str:
    """`node:fs` -> `fs`, `@scope/pkg/deep` -> `@scope/pkg`, `lodash/fp` -> `lodash`."""
    if spec.startswith("node:"):
        spec = spec[5:]
    parts = spec.split("/")
    if spec.startswith("@") and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]
