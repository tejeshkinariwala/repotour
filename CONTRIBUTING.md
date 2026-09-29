# Contributing

## Dev setup

Requires Python 3.10 or later and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tejeshkinariwala/repotour
cd repotour
uv sync --extra dev
uv run repotour --version
```

## Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

CI runs ruff and pytest on Python 3.10 to 3.13. Sample repos for tests are in `tests/fixtures/`. Use invented names ("Acme"), never real project or personal names.

## Adding an analyzer

An analyzer reads one file and returns its facts: header, outline, imports and libraries.

1. Add `src/repotour/analyzers/<language>.py` with a class that follows the protocol in `analyzers/base.py`.
2. Register its suffixes in `analyzers/__init__.py`.
3. Resolve imports to repo-relative paths when the language allows it; treat everything else as a library.
4. Add a fixture under `tests/fixtures/` and tests for outline, imports and header.
5. Add the language to the table in the README and to `CHANGELOG.md`.

Without an analyzer, a file still appears in the tour with its header comment and line count.

## Keeping the skill copy in sync

The skill exists twice:

- `skills/repotour/` is the source. The Claude Code plugin loads it.
- `src/repotour/skill/` is a copy that ships in the Python package. `repotour install-skill` copies from there.

Edit only `skills/repotour/`, then run:

```bash
python scripts/sync_skill.py
```

`python scripts/sync_skill.py --check` exits 1 if the copies differ. CI runs it.

## Leak-check hook

`scripts/leak_check.py` scans tracked and staged files for words in a private denylist. The denylist is outside the repo: `$REPOTOUR_DENYLIST` or `~/.config/repotour/denylist.txt`, one term per line. Install the pre-commit hook once per clone:

```bash
python scripts/leak_check.py --install-hook
```

With no denylist file the check prints a notice and passes.

## Clean-room rule

Write from `docs/SPEC.md`. Do not copy code, text or examples from private projects. No personal data, no hardcoded time zones or locations.

## Pull requests

Keep changes small. Fill in the pull request template. Add tests for new behaviour and a line in `CHANGELOG.md`.
