# CLAUDE.md

## Purpose

RepoTour turns a code repo into one offline HTML page: parts, problems, stories, files with roles, outlines with one-line notes, imports and used-by. The contract is `docs/SPEC.md`. Read it before changing behaviour.

Two layers:
- Engine (`src/repotour/`): deterministic Python CLI. No AI calls, no network.
- Writer: the Claude Code skill in `skills/repotour/`, which writes `.repotour/tour.yaml` and `notes.yaml`.

## Key files

- `docs/SPEC.md`: the specification.
- `src/repotour/cli.py`: commands (build, scan, check, init, install-skill).
- `src/repotour/scan.py`, `analyzers/`: file walking and per-language facts.
- `src/repotour/config.py`: loads and validates the written content.
- `src/repotour/build.py`: builds the data model and warnings. `render.py` injects it into `templates/tour.html`.
- `skills/repotour/`: skill source. `src/repotour/skill/` is a copy; never edit it directly.
- `scripts/sync_skill.py`: copies the skill into the package. `scripts/leak_check.py`: denylist scan.

## Conventions

- Python 3.10+. Only runtime dependency is PyYAML. Do not add others without a reason.
- `uv run pytest` and `uv run ruff check .` must pass.
- After editing `skills/repotour/`, run `python scripts/sync_skill.py`.
- The HTML template is one file with inline CSS and JS, no external requests.
- Writing style in docs and skill text: plain, literal English. No metaphors or hype.

## Clean-room rule

Write everything from the spec. Do not copy code, text, names or examples from any private project. Examples and fixtures use invented names ("Acme") or public open-source repos. No personal data, no private project names, no hardcoded time zones or locations. Run `python scripts/leak_check.py` before committing; never write denylist terms into any repo file.
