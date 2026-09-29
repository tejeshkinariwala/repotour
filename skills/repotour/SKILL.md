---
name: repotour
description: Writes a readable HTML tour of a code repository using the repotour CLI. Use when the user types /repotour (optionally with a path) or asks for a repo tour, a codebase walkthrough, an architecture map, or an onboarding guide for a repo. Creates or updates .repotour/tour.yaml and .repotour/notes.yaml, then builds .repotour/tour.html.
argument-hint: "[path to repo, default .]"
---

# RepoTour writer

Turn a repository into a tour: parts, the problems each part solves, files with roles, user stories that trace real use cases, a reading order, and one-line notes for every function and class. The `repotour` CLI does the deterministic work (scanning, imports, used-by, validation, HTML). You write the human content.

The repo to tour is `$ARGUMENTS` if given, otherwise the current directory. Call it `ROOT` below.

Before writing anything, read `reference/writing-guide.md` (writing rules) and `reference/tour-yaml.md` (file schema and a worked example), both in this skill's folder.

## Workflow

### 1. Check the CLI

Run `repotour --version`. If the command is not found, stop and tell the user to install it with one of:

- `pipx install repotour`
- `uv tool install repotour`
- `pip install repotour`

Then wait for them to confirm.

### 2. Choose what to scan

1. Run `repotour scan ROOT --files-only`. It lists what the engine picks up.
2. Decide what does not belong in the tour: documentation sites, example apps, generated code, vendored code, fixtures. Write `scan.exclude` (and `scan.include` if needed) in `.repotour/tour.yaml` first. Markdown and HTML are not scanned by default; add them with `scan.include` only if a story needs to cite them (for example a templates folder).
3. Run `repotour scan ROOT --files-only` again until the list is what you want to explain.

### 3. Gather facts

- Run `repotour scan ROOT --json`. It lists every file with language, line count, header comment, role, outline (names, line numbers, signatures), in-repo imports, libraries and used-by. Use it instead of opening files to find out what exists and what depends on what. The outline JSON is the source of truth for note keys.
- Read the README, the package manifest, and the entry points (files with the `conductor` role, `main`, `cli`, `app`, `server`).
- Read a file in full only when its header, outline and neighbours do not tell you what it does. Never describe a file you have not understood.
- If `.repotour/tour.yaml` or `.repotour/notes.yaml` already exists, read them first (see "Updating").

**Large repos (more than 300 files).** Do not read everything in one context. Split the repo into 3-8 parts by top-level folder, then start one subagent per part. Each subagent reads its part's files and returns: a purpose line where needed, notes for every outline item in each file, a `_file` note for each test file (tests need nothing else), and 2-3 sentences on what the part does and what it depends on. Merge the results: you write `tour.yaml` from the summaries, and `notes.yaml` from the per-item notes. You do the stories yourself, since they cross parts.

### 4. Write `.repotour/tour.yaml`

Follow `reference/tour-yaml.md`. Targets:

- 3-8 **parts**. Each has a one-line `role`, a `summary`, and `folders` (folder prefixes ending in `/`, never file paths) so new files land in the right part.
- Each part has **problems** phrased as real problems a newcomer would recognise, with `without` (the concrete failure if the code did not exist) and `fix` (how the files solve it, naming the key files).
- Every file belongs to exactly one problem (`files`, or `tests` for test files). Use patterns where a folder is uniform. A file may still appear in the steps of several stories.
- 3-10 **stories**. Each traces one real use case through the code in call order, with the `command` that triggers it and the files each step touches. Cover the main path first, then one or two secondary ones (an admin task, an error path, adding an extension).
- A **guide**: a reading order that starts with the map, then the main story, then the parts.
- YAML safety: write every prose field (`summary`, `without`, `fix`, story `summary`, and step `text` that contains `: `) as a `>-` block scalar. Quote any other value containing `: `, `#`, `{` or `[`. See the examples in `reference/tour-yaml.md`.

**Updating.** If `tour.yaml` exists, edit it instead of rewriting it. Keep existing ids and wording. Add new files to the best-fitting existing problem (or add a problem if none fits), remove files that no longer exist, and change wording only where the code changed. Report what you changed.

The build only catches names that were added or removed. It cannot tell when existing text has become wrong. So when updating, also:
- Find which files changed since the tour was last written (`git log --since` / `git diff` against the commit that last touched `.repotour/`, if git is available), and re-read them.
- Re-check every note, problem `fix` and story step that mentions a changed file against the current code.
- Drop a `_file` note when the file's `header` in the scan output now says the same thing in one clear line.
- Put a test that covers several problems under the problem of the main file it imports.

### 5. Write `.repotour/notes.yaml`

- Keys come from the outline JSON: top-level item names, `Class.method` for methods, and nested children keyed by their own bare name (not `Parent.child`).
- Cover every item kind in the outline: functions, classes, methods, tables, types and interfaces, exported values. `consts` need no notes.
- Once a file has any note, it needs a note for every item. A non-test file with outline items and no entry in `notes.yaml` gets a warning.
- Every non-test file needs a purpose: a `_file` note or a useful header comment. A non-test file with neither gets a warning `no purpose line`.
- Write `_file` for every non-test source file whose `header` in the scan output is not a useful one-line purpose. Headers are often poor: reST titles, license banners, `Copyright` lines, shebangs.
- Test files: notes are optional. Recommend a `_file` only.
- Quote every note that contains `: ` or starts with a special character (`"Returns {a: 1}"`). Unquoted, it breaks the YAML. Quoting every note is fine.
- Note rules are in the writing guide.

### 6. Build and fix

Run `repotour build ROOT`. Read every warning and fix its cause: unplaced files, missing notes, notes for names that no longer exist, patterns that match nothing, files under two problems, empty recommended fields. Errors (unknown part id, duplicate id, YAML syntax) stop the build and must be fixed first. Repeat until there are zero warnings. If a file cannot be explained (for example generated code), add a `scan.exclude` pattern and say why.

### 7. Check the entry points

Zero warnings is necessary, not sufficient. Before finishing, take the public entry points and exports the README names (commands, functions, classes, routes) and confirm each appears in the scan outline and has a note. If the analyzer misses something (for example a dynamically defined function or an unusual export form), do not hide it: say so in your final report to the user.

Then tell the user the output path (`ROOT/.repotour/tour.html`) and offer to run `repotour build ROOT --open`. Mention that `repotour check` can run in CI to keep the tour fresh.

## Writing rules (summary)

Full rules, with examples, are in `reference/writing-guide.md`.

- Plain, literal English. Say what a thing does. No metaphors, no flourish, no praise words.
- Notes are one line and start with a verb: "Checks...", "Returns...", "Raises...".
- A problem title is the problem as a newcomer would meet it, not the name of a module.
- `without` describes a concrete failure. `fix` names the key files.
- Stories follow the actual call order. Check by reading the code, not by guessing.
- Never invent behaviour. If you did not read it, do not describe it.
- State honest gaps: "Today only the import command runs this check."

## Do not

- Do not edit source code in the repo being toured.
- Do not delete `.repotour/` content the user wrote by hand without saying so.
- Do not leave warnings unexplained. If a warning cannot be fixed, say why in your report.
