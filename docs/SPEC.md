# RepoTour specification

RepoTour turns a code repository into one self-contained, offline HTML page that a newcomer can
read in an afternoon. The page explains the repo in four ways:

1. **Parts** - the big areas of the repo, each with the **problems** it solves ("without this..." /
   "the fix") and the files that solve each problem.
2. **Stories** - user stories that follow one use case step by step across files ("a request
   comes in", "I add a new command"), each with the command that starts it.
3. **Files** - every file with its purpose, its **role** (an emoji category such as
   🎬 Conductor or 📐 Rulebook), an outline of its classes and functions with a one-line note per
   item, the in-repo files it imports (and which names), the outside libraries it uses, and the
   files that import it.
4. **Guide** - a suggested reading order.

RepoTour has two layers:

- **Engine (deterministic, no AI):** a Python CLI, `repotour`, that scans the repo, parses
  Python and JavaScript/TypeScript, assigns roles, computes imports / used-by / part-to-part
  dependencies, validates the written content, lists everything stale as warnings, and renders
  the HTML. It works on any repo even with no written content (auto mode).
- **Writer (AI):** a Claude Code skill, `/repotour`, that reads the repo (using
  `repotour scan --json` to get the facts cheaply) and writes the human content:
  `.repotour/tour.yaml` and `.repotour/notes.yaml`. It then runs `repotour build` and fixes
  warnings until there are none.

The engine never calls an AI service and never needs network access.

---

## 1. Repository layout (the RepoTour project itself)

```
repo-tour/
├── pyproject.toml            # hatchling; package "repotour"; entry point repotour = repotour.cli:main
├── README.md  LICENSE (MIT)  CONTRIBUTING.md  CHANGELOG.md  CLAUDE.md  .gitignore
├── src/repotour/
│   ├── __init__.py           # __version__
│   ├── __main__.py           # python -m repotour
│   ├── cli.py                # argparse: build, scan, check, init, install-skill
│   ├── scan.py               # walk the repo, apply include/exclude, .gitignore aware
│   ├── config.py             # load + validate .repotour/tour.yaml and notes.yaml
│   ├── roles.py              # built-in roles and default role rules
│   ├── globs.py              # pattern expansion (fnmatch + {a,b} braces + **)
│   ├── analyzers/
│   │   ├── __init__.py       # registry: suffix -> analyzer
│   │   ├── base.py           # Analyzer protocol + FileFacts dataclasses
│   │   ├── python.py         # stdlib ast
│   │   ├── javascript.py     # JS/TS/JSX/TSX, no third-party parser
│   │   └── generic.py        # any other text file: header comment only
│   ├── build.py              # assemble the data model (section 4) + warnings
│   ├── render.py             # inject JSON into the template, write HTML
│   ├── templates/tour.html   # the single-file viewer
│   └── skill/                # copy of the Claude Code skill, used by install-skill
├── skills/repotour/          # Claude Code skill (plugin layout)
│   ├── SKILL.md
│   └── reference/            # tour-yaml.md, writing-guide.md
├── .claude-plugin/           # plugin.json + marketplace.json so users can /plugin install
├── tests/                    # pytest; tests/fixtures/ holds tiny sample repos (py, ts, mixed)
├── scripts/leak_check.py     # scans tracked files against a denylist kept outside the repo
├── examples/                 # generated demo tours of public open-source repos
└── .github/workflows/ci.yml  # ruff + pytest on 3.10-3.13
```

Runtime dependency: `PyYAML` only. Python >= 3.10. Dev: `pytest`, `ruff`.

---

## 2. CLI

All commands take an optional `PATH` (default `.`), the root of the repo to tour.

| Command | What it does |
|---|---|
| `repotour build [PATH] [--out FILE] [--open] [--strict]` | Builds the tour. Default output: `PATH/.repotour/tour.html`; missing parent folders are created. If the output cannot be written, prints one error line and exits 2. Prints each warning to stderr and a summary line. Exit 0 (or 1 with `--strict` if any warnings). |
| `repotour scan [PATH] [--json] [--files-only]` | Prints the facts the engine extracted: every file with language, lines, header, role, outline (names + line numbers + signature), in-repo imports, libraries, used-by. `--json` for the skill. Without `--json`, a compact human-readable listing. |
| `repotour check [PATH]` | Same validation as build, writes nothing, exit 1 if any warning. For CI and pre-commit. |
| `repotour init [PATH] [--force]` | Writes a starter `.repotour/tour.yaml` (parts guessed from top-level folders, one placeholder problem per part holding its files) and a `notes.yaml` skeleton listing every outlined item with an empty note. Refuses to overwrite without `--force`. |
| `repotour install-skill [--project PATH \| --user] [--force]` | Copies the skill into `PATH/.claude/skills/repotour/` or `~/.claude/skills/repotour/`. Refuses to overwrite an existing target without `--force`; with `--force` it replaces the target. If the target is a symlink, the link is replaced and what it points to is left alone. |
| `repotour --version` | Prints the version. |

---

## 3. Written content (the files the skill writes)

Both files live in `<repo>/.repotour/`. Both are optional. All file references are repo-relative
POSIX paths or patterns. Patterns support `*`, `?`, `[...]`, `**` (any depth) and `{a,b}` braces. An entry that names an
existing file exactly (for example `pages/[id].tsx`) is used as that file before any glob
expansion.

### 3.1 `.repotour/tour.yaml`

```yaml
project:
  name: Acme API                     # shown as the page title
  tagline: One sentence on what this repo is for.
  overview: >-                       # optional, 1-3 short paragraphs for the home page
    ...
  repo_url: https://github.com/acme/api   # optional; enables "view source" links (blob/<branch>/<path>#L<line>)
  branch: main                       # optional, default main

scan:                                # optional
  include: ["**/*"]                  # default: every text file with a known suffix (see 5.1)
  exclude: ["vendor/**", "**/*.min.js"]   # added to the built-in excludes

roles: []                            # optional: extra roles or overrides {id, emoji, name, meaning}
role_rules:                          # optional; checked BEFORE the built-in rules, first match wins
  - {role: conductor, match: ["bin/*", "src/cli.py"]}

parts:
  - id: api                          # short slug, unique
    name: API layer                  # display name
    role: Turns HTTP requests into calls on the domain   # one line: the job of this part
    folders: [src/api/, src/routes/] # used to place new, unlisted files (longest prefix wins)
    summary: >-
      2-4 sentences in plain language.
    color: "#3b82f6"                 # optional; otherwise from a fixed palette in order

problems:
  - id: A1                           # unique; convention: part initial + number
    part: api
    title: A request can arrive with any shape of body   # the problem, phrased as a problem
    without: >-                      # what goes wrong if this code did not exist
      ...
    fix: >-                          # how the files below solve it, naming the key files
      ...
    files: [src/api/validate.py, "src/api/schemas/*.py"]
    tests: ["tests/api/test_validate.py"]

stories:
  - id: S1
    act: "Act 1: Serve a request"    # optional grouping heading
    title: A user signs up
    command: curl -X POST localhost:8000/signup   # optional; how to trigger it
    summary: One or two sentences.
    steps:
      - text: The router matches /signup and calls the handler.
        files: [src/routes/users.py]
      - text: ...
        files: [...]

guide:                               # suggested reading order; each item has text and optionally a story or part
  - text: Start with the map; the repo has three parts.
  - story: S1
    text: the main request path. Everything else supports it.
  - part: api
    text: the shared rules you met in S1.
```

Every file the engine sees must be listed under exactly one problem (`files` or `tests`).
Files not listed are not dropped: they are shown on an automatic "Not yet placed" problem inside
the part their folder suggests, and each one produces a warning.

### 3.2 `.repotour/notes.yaml`

One-line notes for the outline of each file, plus an optional one-line file purpose.

```yaml
src/api/validate.py:
  _file: Checks request bodies against the schemas before any handler runs.   # optional; overrides the header comment
  ValidationError: Error raised with the list of bad fields.
  validate: Checks one body against one schema and returns the cleaned value.
  Validator: Holds compiled schemas so each is parsed once.
  Validator.check: Validates and returns the cleaned body or raises.
  _coerce: Turns "1" into 1 and "true" into True where the schema asks.
```

Keys are item names from the outline: top-level items (functions, classes, tables, types,
exported values), `Class.method` for methods, and nested children keyed by their own bare name
(see 5.3). A file with at least one note must have a note for every item; the engine warns
for each missing one and for each note whose name no longer exists. In written mode, a non-test
file (role other than `test`) that has outline items and no entry in notes.yaml gets one warning
(see 3.3). Test files are exempt.

### 3.3 Validation

Errors (stop the build, exit 2, message names the file and the key):
YAML syntax error; a problem naming an unknown part; a role rule naming an unknown role;
duplicate part / problem / story ids; a guide item naming an unknown story or part.
Only ids and references are errors; other fields never stop the build (see the warnings below).

Warnings (build continues; each is printed and also shown on the page in a warnings panel):
- pattern matches nothing / no such file
- a file listed under two problems (kept under the first)
- a file not listed under any problem
- a story step file that is not under any problem
- notes.yaml: file has notes but is not in the repo or not outlined
- notes.yaml: missing note for an item; note for a name that no longer exists
- notes.yaml (written mode only): `notes.yaml: no notes for <file> (<n> items)` for a non-test file
  with outline items and no entry in notes.yaml; `<n>` counts every noteable key (items, methods,
  children). Test files are exempt.
- written mode only: `<file>: no purpose line (add _file in notes.yaml or a header comment)` for a
  non-test file whose final `purpose` (the `_file` note, else the header) is empty. Test files are
  exempt.
- an empty recommended field: part `name` or `summary`, problem `title` or `fix`, story `title` or
  `steps` (`tour.yaml: part 'api': summary is empty`)
- a part with no problems; a problem with no files

---

## 4. Data model passed to the template

`build.py` produces one JSON object. `render.py` replaces the literal `/*REPOTOUR_DATA*/null` in
the template with it (with every `<` escaped as `\u003c`). The template must render every field below and
must not assume any other field exists.

```jsonc
{
  "tool": {"name": "RepoTour", "version": "0.1.0", "url": "https://github.com/<owner>/repotour"},
  "mode": "written" | "auto",            // auto = no tour.yaml was found
  "project": {"name": "...", "tagline": "...", "overview": "...", "repo_url": null, "branch": "main"},
  "built_at": "2026-09-29 14:03 +08:00",   // local time with UTC offset, ISO-like, no zone name
  "stats": {"files": 120, "lines": 15000, "languages": {"python": 80, "typescript": 30, "yaml": 10}},
  "roles": [{"id": "conductor", "emoji": "🎬", "name": "Conductor", "meaning": "..."}],
  "parts": [{"id": "api", "name": "...", "role": "...", "summary": "...", "folders": ["src/api/"], "color": "#3b82f6",
             "problems": ["A1", "A2"], "files": 14, "lines": 2100}],
  "part_links": [{"from": "api", "to": "core", "imports": 12}],   // part A files import part B files, count of file->file edges
  "problems": [{"id": "A1", "part": "api", "title": "...", "without": "...", "fix": "...",
                "files": ["src/api/validate.py"], "tests": ["tests/api/test_validate.py"], "placeholder": false}],
  "stories": [{"id": "S1", "act": "...", "title": "...", "command": "...", "summary": "...",
               "steps": [{"text": "...", "files": ["src/routes/users.py"]}]}],
  "guide": [{"text": "...", "story": "S1" | null, "part": "api" | null}],
  "files": {
    "src/api/validate.py": {
      "lang": "python",
      "lines": 120,
      "purpose": "one line, from notes _file or the header comment/docstring",
      "role": "guard",
      "problem": "A1",
      "part": "api",
      "stories": ["S1"],
      "outline": {                          // absent for files no analyzer outlines
        // kind: "function" | "class" | "table" | "type" | "const" | "value"
        "items": [ {"name": "Validator", "kind": "class", "line": 10, "signature": "class Validator(Base)",
                    "note": "...", "exported": true,
                    "methods": [{"name": "check", "line": 14, "signature": "check(self, body)", "note": "..."}],
                    "calls": ["validate"],              // other top-level items this one references
                    "children": [ /* same shape: private helpers used only by this item */ ] } ],
        "consts": ["MAX_BODY"]              // public module-level constants
      },
      "imports": [{"file": "src/api/schemas/user.py", "names": ["UserSchema"]}],
      "libs": ["pydantic", "re"],
      "used_by": ["src/routes/users.py"]
    }
  },
  "warnings": ["..."]
}
```

---

## 5. Engine behaviour

### 5.1 Scanning
- Walk from the repo root. Always skip, at any depth: `.git`, `.hg`, `.svn`, `node_modules`,
  `.venv`, `venv`, `__pycache__`, any folder named `*_cache`, `.tox`, `.repotour`, `.next`, `.nuxt`.
- In a git repo (`.git` exists and git is on PATH), the file list is
  `git ls-files --cached --others --exclude-standard`, so `.gitignore` decides about everything
  else. `build/ dist/ target/ vendor/ env/ coverage/` are not skipped there: a tracked
  `vendor/` or `build/` folder is scanned (use `scan.exclude` to drop it).
- Outside git (not a git repo, or git is unavailable), walk the folder and also skip
  `build`, `dist`, `target`, `vendor`, `env` and `coverage` at any depth.
- Default suffixes: `.py .pyi .js .jsx .mjs .cjs .ts .tsx .mts .cts .sh .bash .zsh .yaml .yml
  .toml .json .ini .cfg .sql`. Markdown is **not** included by default (docs are not code), nor are
  lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`) or
  `*.min.js`, `*.map`, `*.d.ts` files under `node_modules`. Files larger than 1 MB are skipped
  with a warning.
- `scan.include` / `scan.exclude` in tour.yaml adjust this.
- The default suffix list is defined once, as `DEFAULT_SUFFIXES` in `repotour.analyzers`, and
  `scan.py` imports it.

### 5.2 Header / purpose
Order: notes `_file` → Python module docstring (first paragraph) → leading `#` comment block
(after a shebang / encoding line) → leading `//` or `/* */` / `/** */` block in JS/TS → YAML/TOML
leading `#` block → empty. Joined into one line, trimmed to 300 characters.

### 5.3 Python analyzer (stdlib `ast`)
- Outline: top-level functions (sync and async), classes (with bases and methods), and
  **function tables**: a module-level assignment whose value references top-level function
  names (a dispatch dict or list) is shown as an item of kind `table`.
- Nesting: a private item (name starts with `_`) referenced by exactly one other top-level item
  is shown as a child of that item, so the outline reads top-down from the entry points. Break
  reference cycles.
- `calls`: other top-level items an item references (excluding its children), in line order.
- `exported`: true unless the name starts with `_` (or it is not in `__all__` when `__all__` exists).
- `signature`: `name(args)` rendered with `ast.unparse` of the arguments, without annotations
  longer than 40 characters.
- Imports: `import x`, `from x import y`, relative imports, and imports inside functions. Resolve
  to in-repo files by trying `a/b.py`, `a/b/__init__.py`, also under `src/`, and under each
  top-level folder that contains an `__init__.py` root package. `from pkg import submodule`
  resolves to the submodule file. Anything unresolved counts as a library (top-level name).
  Skip `__future__`.
- Syntax errors: the file is listed without an outline, and a warning is recorded.

### 5.4 JavaScript / TypeScript analyzer (no third-party parser)
- First strip comments and string/template-literal contents (keep positions and line numbers)
  with a small state-machine lexer, then match with regexes and brace counting.
- Outline: top-level `function` / `async function` / `function*`, `class` (with methods, getters,
  setters, static), `const|let|var name = (…) =>` / `= function` / `= async (…) =>`,
  top-level `interface`, `type`, `enum` (TS) as kind `type`, and `export default` forms.
  React components are just functions. `exported` from the `export` keyword or a later
  `export { a, b }`.
- Exported top-level `const`/`let` bindings whose value is not a function literal are outlined too.
  After stripping `as …` / `satisfies …` and wrapping parens, an initializer that is a function or
  arrow, or an identifier naming a top-level function item, gives kind `function`
  (with that function's parameters); anything else gives kind `value`. Non-exported
  non-function consts stay out, and UPPERCASE constants are listed in `consts` only.
- Overloads (`function f(a): X; function f(a, b): Y; function f(...) {…}`, also methods) are one
  item with the implementation's signature (the first signature if there is no implementation).
  Signatures are one line, keep generics, and are cut at 120 characters with `…`.
- Path aliases come from the nearest `tsconfig.json`/`jsconfig.json` above each file (following a
  relative `extends` one level), and only if the file matches that config's `include`/`exclude`.
- Imports: `import … from '…'`, `import '…'`, `export … from '…'`, `require('…')`, dynamic
  `import('…')`. Named imports are recorded as `names`. Relative specifiers resolve against the
  file's folder trying the exact path, then the suffixes `.ts .tsx .js .jsx .mjs .cjs .mts .cts`,
  then `/index.*`; a `.js` specifier also tries `.ts`/`.tsx` (TS ESM style). If `tsconfig.json` or
  `jsconfig.json` has `compilerOptions.baseUrl`/`paths`, apply them (simple `*` wildcard only).
  Bare specifiers are libraries (scope-aware: `@scope/pkg`). `node:` prefix stripped.
- `calls` and nesting follow the same rules as Python using identifier references in the body.

### 5.5 Other files
`generic.py` gives language (from suffix), line count and header only.

### 5.6 Roles
Built-in roles (id, emoji, name, meaning):

| id | emoji | name | meaning |
|---|---|---|---|
| conductor | 🎬 | Conductor | Starts things and calls other files in order: entry points, CLIs, servers, scripts, build steps. |
| rulebook | 📐 | Rulebook | Defines what things must look like: types, schemas, interfaces, base classes, constants, registries. Does little work itself. |
| worker | ⚙️ | Worker | Does the actual work: the core logic, algorithms and transformations. |
| guard | 🛡️ | Guard | Checks something and refuses or stops when it is wrong: validation, auth, permissions, limits. |
| storekeeper | 📦 | Storekeeper | Saves and loads data: databases, caches, files, queues, migrations. |
| courier | 🔌 | Courier | Talks to the outside world: HTTP clients, API adapters, SDK wrappers, messaging. |
| analyst | 🔍 | Analyst | Measures and reports: metrics, logging, statistics, reports, charts. |
| face | 🖼️ | Face | What a user sees: UI components, pages, views, templates, styles. |
| config | 🗂️ | Settings | A file of settings or records that code reads. |
| helper | 🧩 | Helper | Small shared utilities and package markers. |
| test | 🧪 | Test | Automated test that checks other files still behave as before. |

Default rules, first match wins, patterns match the repo-relative path (case-insensitive) after
the user's `role_rules`:
1. test: `tests/**`, `test/**`, `**/__tests__/**`, `**/test_*.py`, `**/*_test.py`, `**/*.test.*`, `**/*.spec.*`, `**/conftest.py`
2. config: `*.yaml`, `*.yml`, `*.toml`, `*.json`, `*.ini`, `*.cfg`, `**/*.config.{js,ts,mjs,cjs}`, `**/settings.py`, `**/config.py`, `**/config/**`
3. helper: `**/__init__.py`, `**/index.{js,ts}` whose body is only re-exports, `**/util*`, `**/helper*`, `**/common*`, `**/_util*`
4. conductor: `**/__main__.py`, `**/main.{py,js,ts}`, `**/cli*.{py,js,ts}`, `**/app.{py,js,ts}`, `**/server.{py,js,ts}`, `**/manage.py`, `bin/**`, `scripts/**`, `*.sh`, `**/*.sh`, `**/commands/**`
5. face: `**/*.{jsx,tsx}`, `**/components/**`, `**/pages/**`, `**/views/**`, `**/templates/**`, `**/ui/**`
6. guard: `**/*valid*`, `**/*auth*`, `**/*guard*`, `**/*permission*`, `**/*policy*`, `**/*check*`, `**/middleware*`
7. storekeeper: `**/*store*`, `**/*cache*`, `**/*db*`, `**/*database*`, `**/*repo*`, `**/*storage*`, `**/models/**`, `**/migrations/**`, `**/*persist*`
8. courier: `**/*client*`, `**/*api*`, `**/*http*`, `**/*adapter*`, `**/*integration*`, `**/*webhook*`, `**/*sdk*`
9. analyst: `**/*report*`, `**/*metric*`, `**/*stat*`, `**/*log*`, `**/*analytic*`, `**/*telemetry*`
10. rulebook: `**/*types*`, `**/*schema*`, `**/*model*`, `**/*interface*`, `**/*const*`, `**/*enum*`, `**/*base*`, `**/*registry*`, `**/*.d.ts`, `**/*.pyi`
11. worker: everything else

### 5.7 Auto mode (no tour.yaml)
- Parts = top-level folders (a single `src/` wrapper is looked through), plus a part named
  "Root" for top-level files; tests go in a "Tests" part.
- One placeholder problem per part (`placeholder: true`, title "Files in <folder>"), holding its files.
- No stories and no guide; the page shows a banner explaining how to add written content
  (`/repotour` in Claude Code, or `repotour init`).
- Auto mode produces no "not in any problem" warnings.

### 5.8 Time
`built_at` uses the machine's local time zone with its numeric UTC offset. No hardcoded zone.

---

## 6. The page (templates/tour.html)

One file: inline CSS and JS, no external requests, no CDN, works from `file://`. Vanilla JS, no
build step. Must stay fast with 3,000 files.

Views, routed by URL hash so the back button and links work (`#/`, `#/part/<id>`,
`#/story/<id>`, `#/file/<path>`, `#/files?q=...&role=...`):

- **Home.** Title, tagline, overview, stats, the auto-mode banner if relevant, a **map** of parts
  (cards coloured per part, with file/line counts, arrows or a list for `part_links` showing
  which parts depend on which), the role legend (emoji + name + meaning), the stories list
  grouped by act, and "How to read this tour" with the guide as a numbered list of links.
- **Part.** Name, role, summary, then each problem as a card: title, "Without it" and "The fix"
  paragraphs, and its files as rows (role emoji, path, purpose), then tests.
- **Story.** Title, command (copy button), summary, numbered steps; each step lists its files
  as rows. Previous/next story links.
- **All files.** Search box (path, purpose, function names and notes), filter chips by role,
  part and language; grouped by folder as a collapsible tree; rows show role emoji, path, lines,
  purpose.
- **File.** Path (with "view source" link when repo_url is set), role badge, part and problem
  links, purpose, the stories that use it, then **Inside the file**: the outline tree
  (kind icon, name, signature, line number, one-line note; children indented; methods under
  classes; "calls →" links to sibling items), public constants, then **Imports** (file links with
  imported names), **Libraries**, and **Used by**. Files with notes missing show a small
  "notes missing" marker.
- **Warnings** panel reachable from the header when `warnings` is non-empty, count badge.
- Header: project name, nav (Home, Stories, Parts, All files), a global search, light/dark toggle
  (respects prefers-color-scheme), footer "Built with RepoTour vX on <built_at>".
- Clicking any file path anywhere opens its file view. Keyboard: `/` focuses search, `Esc` clears.
- Accessible: real links and buttons, focus styles, sufficient contrast. Readable typography:
  system font stack, ~70ch line length for prose.

---

## 7. Clean-room and privacy rules (for everyone working on this repo)

- Write everything from this spec. Do not copy code, text, names or examples from any private
  project. Examples, fixtures and demo tours use invented names ("Acme") or public open-source repos.
- No personal data, no private project names, no hardcoded time zones or locations.
- `scripts/leak_check.py` reads a denylist from `$REPOTOUR_DENYLIST` or
  `~/.config/repotour/denylist.txt` (never from inside the repo), checks every tracked and
  staged file (`git ls-files` + untracked not ignored) case-insensitively for whole-word matches,
  prints file:line:term for each hit, and exits 1 on any hit. If no denylist exists it prints a
  notice and exits 0. `python scripts/leak_check.py --install-hook` installs it as a git
  pre-commit hook.
