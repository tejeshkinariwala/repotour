# `.repotour/tour.yaml` and `.repotour/notes.yaml`

Both files live in `<repo>/.repotour/`. All file references are repo-relative POSIX paths or patterns. Patterns support `*`, `?`, `[...]`, `**` (any depth) and `{a,b}` braces.

## Required, recommended, optional

The engine checks three levels. Use this table, not guesswork.

| Level | What | Effect when wrong |
|---|---|---|
| Required (error, exit 2) | `id` on every part, problem and story; `part` on every problem, naming an existing part; unique ids; `role` in each `role_rules` entry naming a known role; `story` / `part` in a guide item naming an existing story / part | Build stops |
| Recommended (warning) | part `name` and `summary`; problem `title` and `fix`; story `title` and `steps` | Build continues, one warning per empty field |
| Placement (warning) | every scanned file under exactly one problem; a problem with no files; a part with no problems; patterns that match nothing | Build continues |
| Optional | everything else: `project.*`, part `role` / `folders` / `color`, problem `without` / `tests`, story `act` / `command` / `summary`, `guide`, `scan`, `roles`, `role_rules` | None |

The tables below mark a field "yes" when a good tour needs it, even if the engine only warns or does not check it. Write all of them: zero warnings is the target.

## tour.yaml keys

### `project`

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Page title. |
| `tagline` | yes | One sentence on what the repo is for. |
| `overview` | no | 1-3 short paragraphs for the home page. |
| `repo_url` | no | Enables "view source" links (`blob/<branch>/<path>#L<line>`). |
| `branch` | no | Default `main`. |

### `scan` (optional)

| Key | Meaning |
|---|---|
| `include` | Globs to include. Default: every text file with a known suffix. Markdown and HTML are not scanned by default; add them here (for example `templates/**`) if a story needs to cite them. |
| `exclude` | Globs added to the built-in excludes: documentation sites, example apps, generated code, vendored code. |

Decide these first: run `repotour scan --files-only`, write `scan`, then run `repotour scan --json`.

In a git repo the file list comes from git, so `build/`, `dist/`, `vendor/` and similar folders are scanned if git tracks them. Exclude them explicitly when they are not source.

A path that names an existing file exactly (`pages/[id].tsx`) is used as that file even though it contains glob characters.

### `roles` and `role_rules` (optional)

- `roles`: extra roles or overrides, each `{id, emoji, name, meaning}`.
- `role_rules`: `{role, match: [globs]}` entries, checked before the built-in rules, first match wins. Use them when the automatic role is wrong for a group of files. The `role` must be a known role id (`conductor`, `rulebook`, `worker`, `guard`, `storekeeper`, `courier`, `analyst`, `face`, `config`, `helper`, `test`, or one you defined).

### `parts` (3-8)

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Short unique slug. |
| `name` | yes | Display name. |
| `role` | yes | One line: the job of this part. |
| `folders` | yes | Folder prefixes ending in `/`, used to place new, unlisted files (longest prefix wins). Never file paths: `src/acme/cli.py` is wrong, `src/acme/cli/` is right. |
| `summary` | yes | 2-4 sentences, plain language. |
| `color` | no | Hex colour; otherwise from a fixed palette in order. |

### `problems`

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique. Convention: part initial plus number (`A1`). |
| `part` | yes | Id of an existing part. |
| `title` | yes | The problem, phrased as a problem a newcomer would recognise. |
| `without` | yes | The concrete failure if this code did not exist. |
| `fix` | yes | How the files solve it, naming the key files. |
| `files` | yes | Files or patterns that solve the problem. |
| `tests` | no | Test files or patterns for this problem. |

Every file the engine sees must be listed under exactly one problem (`files` or `tests`). Unlisted files appear under an automatic "Not yet placed" problem and each produces a warning. A file listed under two problems is kept under the first and produces a warning.

### `stories` (3-10)

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique (`S1`). |
| `act` | no | Grouping heading, for example `"Act 1: Serve a request"`. |
| `title` | yes | What the user does or what happens. |
| `command` | no | How to trigger it (CLI call, `curl`, test command). |
| `summary` | yes | One or two sentences. |
| `steps` | yes | List of `{text, files}` in real call order. Each file must also be under some problem. A file can appear in the steps of several stories; it belongs to exactly one problem. |

### `guide`

A list of reading-order items: `{text}` alone, or with `story: <id>` or `part: <id>`. The engine renders `text` as a link label when `story` or `part` is set, so write it to continue the link: "the main request path. Everything else supports it."

## notes.yaml

```yaml
src/api/validate.py:
  _file: Checks request bodies against the schemas before any handler runs.
  ValidationError: Error raised with the list of bad fields.
  validate: Checks one body against one schema and returns the cleaned value.
  Validator: Holds compiled schemas so each is parsed once.
  Validator.check: Validates and returns the cleaned body or raises.
  _coerce: Turns "1" into 1 and "true" into True where the schema asks.
```

- The outline JSON from `repotour scan --json` is the source of truth for keys. Keys are top-level item names, `Class.method` for methods, and nested children keyed by their own bare name (a private helper nested under `validate` is keyed `_coerce`, not `validate._coerce`).
- Notes cover every item kind in the outline: functions, classes, methods, tables (dispatch dicts and lists), types and interfaces, exported values. `consts` need no notes.
- `_file` overrides the header comment as the file purpose. Write it for every non-test source file whose `header` in the scan output is not a useful one-line purpose (reST titles, license banners and copyright lines are common).
- A file with at least one note must have a note for every item. The engine warns for each missing item and for each note whose name no longer exists.
- Written mode only: a non-test file with outline items and no entry in notes.yaml gets one warning, `notes.yaml: no notes for <file> (<n> items)`.
- Test files: notes are optional. Recommend a `_file` only.
- Quote values that contain `: `, `#`, `{` or `[`, or that start with a special character.

## YAML safety

Prose breaks YAML easily. Rules:

- Use a `>-` block scalar for every prose field: part `summary`, problem `without` and `fix`, story `summary`, and step `text` when it contains `: `.
- Quote any other value that contains `: `, `#`, `{` or `[`, for example `act: "Act 1: Serve a request"`.
- After writing, run `repotour check`. A YAML syntax error names the file.

```yaml
problems:
  - id: A1
    part: api
    title: A request can arrive with any shape of body
    without: >-
      Each handler would parse the body itself.
    fix: >-
      `validate.py` checks the body and raises `ValidationError`.
    files: [src/acme/api/validate.py]
stories:
  - id: S1
    act: "Act 1: Everyday use"
    title: A client creates an invoice
    summary: >-
      The request is checked and saved.
    steps:
      - text: >-
          The route calls validate: a body with a bad field is rejected with a 400.
        files: [src/acme/api/routes.py]
```

## Errors and warnings

Errors stop the build (exit 2): YAML syntax error; a missing `id`; a problem with a missing or unknown part; a role rule naming an unknown role; duplicate part, problem or story ids; a guide item naming an unknown story or part.

Warnings (build continues, each is printed and shown on the page): a pattern that matches nothing; a file under two problems; a file under no problem; a story step file under no problem; notes for a file that is missing or not outlined; a missing note for an item; a note for a name that no longer exists; a part with no problems; a problem with no files; a non-test file with outline items and no entry in notes.yaml; an empty part `name` or `summary`, problem `title` or `fix`, story `title` or `steps`.

Fix every warning. The target is zero.

## Worked example

A small invented repo, "Acme Invoices": a Flask-style service that takes invoice requests, validates them, stores them and renders PDFs.

```
acme-invoices/
├── src/acme/
│   ├── cli/main.py
│   ├── api/routes.py
│   ├── api/validate.py
│   ├── api/schemas.py
│   ├── store/db.py
│   ├── store/migrations/001_init.sql
│   └── render/pdf.py
└── tests/
    ├── test_validate.py
    └── test_render.py
```

`.repotour/tour.yaml`:

```yaml
project:
  name: Acme Invoices
  tagline: A small service that accepts invoice requests, stores them and renders PDFs.
  overview: >-
    Clients post invoice data to an HTTP endpoint. The service checks the data,
    saves it in SQLite and can render any saved invoice as a PDF.
  repo_url: https://github.com/acme/invoices
  branch: main

parts:
  - id: api
    name: API layer
    role: Turns HTTP requests into calls on the store and the renderer
    folders: [src/acme/api/]
    summary: >-
      Routes receive requests. Each body is checked against a schema before a
      handler sees it. Handlers call the store and the renderer.
  - id: store
    name: Storage
    role: Saves and loads invoices
    folders: [src/acme/store/]
    summary: >-
      One SQLite database with a single invoices table. Migrations create it.
  - id: render
    name: PDF rendering
    role: Turns a saved invoice into a PDF
    folders: [src/acme/render/]
    summary: >-
      Builds the PDF page by page from an invoice record.
  - id: cli
    name: Command line
    role: Starts the server and runs one-off tasks
    folders: [src/acme/cli/]
    summary: >-
      The `acme` command starts the server and can render an invoice from the
      terminal.

problems:
  - id: A1
    part: api
    title: A request can arrive with any shape of body
    without: >-
      Each handler would parse the body itself. A missing field would surface
      as a KeyError inside a handler and return a 500 instead of a 400.
    fix: >-
      `validate.py` checks the body against a schema from `schemas.py` and
      raises `ValidationError` with the list of bad fields. Handlers only see
      cleaned values.
    files: [src/acme/api/validate.py, src/acme/api/schemas.py]
    tests: [tests/test_validate.py]
  - id: A2
    part: api
    title: Each URL must reach the right handler
    without: >-
      There would be no single place that says which URL runs which code.
    fix: >-
      `routes.py` registers one function per URL and calls `validate` then the
      store or the renderer.
    files: [src/acme/api/routes.py]
  - id: S1
    part: store
    title: Invoices must survive a restart
    without: >-
      Invoices would live in memory and disappear when the server stops.
    fix: >-
      `db.py` writes each invoice to SQLite. The migration in `001_init.sql`
      creates the table on first start.
    files: [src/acme/store/db.py, "src/acme/store/migrations/*.sql"]
  - id: R1
    part: render
    title: Clients want a printable document, not JSON
    without: >-
      Users would copy numbers into a word processor by hand.
    fix: >-
      `pdf.py` lays out the invoice header, the line items and the total.
      Only one page size (A4) is supported today.
    files: [src/acme/render/pdf.py]
    tests: [tests/test_render.py]
  - id: C1
    part: cli
    title: Someone has to start the service
    without: >-
      There would be no command to run the server or render a PDF from a shell.
    fix: >-
      `cli/main.py` parses the command line and either starts the server or calls
      `render_invoice` for one invoice.
    files: [src/acme/cli/main.py]

stories:
  - id: S1
    act: "Act 1: Everyday use"
    title: A client creates an invoice
    command: >-
      curl -X POST localhost:8000/invoices -d '{"customer": "Acme", "total": 120}'
    summary: >-
      The request is checked, saved, and the new invoice id is returned.
    steps:
      - text: The route for POST /invoices receives the request and calls validate.
        files: [src/acme/api/routes.py]
      - text: validate checks the body against the invoice schema and raises on bad fields.
        files: [src/acme/api/validate.py, src/acme/api/schemas.py]
      - text: The route passes the cleaned body to the store, which inserts a row and returns its id.
        files: [src/acme/store/db.py]
  - id: S2
    act: "Act 1: Everyday use"
    title: A user downloads an invoice as a PDF
    command: acme render 42 --out invoice-42.pdf
    summary: >-
      The CLI loads the invoice and writes a PDF file.
    steps:
      - text: The CLI parses "render 42" and loads invoice 42 from the store.
        files: [src/acme/cli/main.py, src/acme/store/db.py]
      - text: render_invoice builds the PDF. Only A4 is supported today.
        files: [src/acme/render/pdf.py]

guide:
  - text: Start with the map; the repo has four parts.
  - story: S1
    text: the main request path. Everything else supports it.
  - part: api
    text: the rules a request must pass, met in the first story.
  - story: S2
    text: the second way in, from the command line.
```

`.repotour/notes.yaml`:

```yaml
src/acme/api/validate.py:
  _file: Checks request bodies against the schemas before any handler runs.
  ValidationError: Error raised with the list of bad fields.
  validate: Checks one body against one schema and returns the cleaned value.
  _coerce: Turns "1" into 1 and "true" into True where the schema asks.
src/acme/render/pdf.py:
  _file: Builds a one-page A4 PDF from an invoice record.
  render_invoice: "Writes the PDF for one invoice: returns the file path."
tests/test_validate.py:
  _file: Checks that bad bodies are rejected with the list of bad fields.
```

Every non-test file with outline items needs an entry, so a real notes.yaml also has entries for `routes.py`, `schemas.py`, `db.py` and `cli/main.py`.
