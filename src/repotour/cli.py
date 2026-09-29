# The `repotour` command line: build, scan, check, init, install-skill and --version.
# Exit codes: 0 ok, 1 warnings under --strict / check, 2 error (message names the file and key).
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any

from repotour import __version__
from repotour.build import build_data, imports_json, outline_json
from repotour.config import Config, ConfigError, load_config
from repotour.init_cmd import init_project
from repotour.install import InstallError, install_skill
from repotour.notes import apply_notes
from repotour.render import RenderError, write_html
from repotour.repo import RepoFacts, collect_facts
from repotour.roles import merge_roles


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except (ConfigError, RenderError, InstallError) as err:
        print(f"repotour: error: {err}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repotour", description="Turn a code repo into a readable HTML tour."
    )
    parser.add_argument("--version", action="version", version=f"repotour {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build the tour HTML")
    _add_path(build)
    build.add_argument("--out", type=Path, help="output file (default: PATH/.repotour/tour.html)")
    build.add_argument("--open", action="store_true", help="open the result in a browser")
    build.add_argument("--strict", action="store_true", help="exit 1 if there are any warnings")
    build.add_argument("--template", type=Path, help=argparse.SUPPRESS)

    scan = sub.add_parser("scan", help="print the facts the engine extracted")
    _add_path(scan)
    scan.add_argument("--json", action="store_true", help="machine-readable output")
    scan.add_argument("--files-only", action="store_true", help="only list the files")

    check = sub.add_parser("check", help="validate without writing; exit 1 on warnings")
    _add_path(check)

    init = sub.add_parser("init", help="write a starter tour.yaml and notes.yaml")
    _add_path(init)
    init.add_argument("--force", action="store_true", help="overwrite existing files")

    skill = sub.add_parser("install-skill", help="install the /repotour Claude Code skill")
    where = skill.add_mutually_exclusive_group()
    where.add_argument("--project", type=Path, metavar="PATH", help="install into PATH/.claude/skills")
    where.add_argument("--user", action="store_true", help="install into ~/.claude/skills")
    skill.add_argument("--force", action="store_true", help="replace an existing install")
    return parser


def _add_path(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "path", nargs="?", default=".", type=Path, metavar="PATH", help="repo root (default: .)"
    )


def _root(args: argparse.Namespace) -> Path:
    root: Path = args.path
    if not root.is_dir():
        raise ConfigError(f"{root}: not a folder")
    return root.resolve()


def _print_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)


# ---------------------------------------------------------------- commands


def _build(args: argparse.Namespace) -> int:
    root = _root(args)
    data = build_data(root)
    out = args.out or root / ".repotour" / "tour.html"
    write_html(data, out, args.template)
    _print_warnings(data["warnings"])
    stats, count = data["stats"], len(data["warnings"])
    print(f"Built {out} ({stats['files']} files, {stats['lines']} lines, {count} warnings)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 1 if args.strict and count else 0


def _check(args: argparse.Namespace) -> int:
    data = build_data(_root(args))
    _print_warnings(data["warnings"])
    count = len(data["warnings"])
    print("No warnings." if count == 0 else f"{count} warnings.")
    return 1 if count else 0


def _init(args: argparse.Namespace) -> int:
    root = _root(args)
    for path in init_project(root, args.force):
        print(f"Wrote {path}")
    return 0


def _install_skill(args: argparse.Namespace) -> int:
    project = None if args.user else (args.project or Path("."))
    target = install_skill(project.resolve() if project else None, args.force)
    print(f"Installed the skill into {target}")
    return 0


def _scan(args: argparse.Namespace) -> int:
    root = _root(args)
    config = load_config(root)
    repo = collect_facts(root, config)
    if args.files_only:
        _print_paths(repo.files, args.json)
        return 0
    warnings = repo.warnings + apply_notes(repo, config.notes)
    if args.json:
        print(json.dumps(scan_json(repo, config, warnings), indent=2, ensure_ascii=False))
    else:
        print(_scan_text(repo))
    return 0


def _print_paths(paths: list[str], as_json: bool) -> None:
    print(json.dumps(paths, indent=2) if as_json else "\n".join(paths))


def scan_json(repo: RepoFacts, config: Config, warnings: list[str]) -> dict[str, Any]:
    """The facts for the skill: one entry per file with the SPEC section 4 keys plus path and header."""
    files = []
    for path in repo.files:
        facts = repo.facts[path]
        files.append(
            {
                "path": path,
                "header": facts.header,
                "lang": facts.lang,
                "lines": facts.lines,
                "role": repo.roles[path],
                "outline": outline_json(facts) if facts.items is not None else None,
                "imports": imports_json(facts),
                "libs": facts.libs,
                "used_by": repo.used_by.get(path, []),
            }
        )
    return {
        "root": repo.root.name,
        "mode": "written" if config.tour else "auto",
        "roles": merge_roles(config.tour.roles if config.tour else []),
        "files": files,
        "warnings": warnings,
    }


HANDLERS = {
    "build": _build,
    "scan": _scan,
    "check": _check,
    "init": _init,
    "install-skill": _install_skill,
}


def _scan_text(repo: RepoFacts) -> str:
    emoji = {r["id"]: r["emoji"] for r in merge_roles([])}
    lines: list[str] = []
    for path in repo.files:
        facts = repo.facts[path]
        role = emoji.get(repo.roles[path], "")
        lines.append(f"{role} {path}  [{facts.lang}, {facts.lines} lines]")
        if facts.header:
            lines.append(f"    {facts.header}")
        for item in facts.items or []:
            lines.append(f"    {item.line:>5}  {item.signature}")
        if facts.imports:
            lines.append("    imports: " + ", ".join(sorted(facts.imports)))
        if facts.libs:
            lines.append("    libs: " + ", ".join(facts.libs))
        if repo.used_by.get(path):
            lines.append("    used by: " + ", ".join(repo.used_by[path]))
    return "\n".join(lines)
