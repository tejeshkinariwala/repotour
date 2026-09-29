## What this changes

## Why

## Checklist
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run pytest` passes, with tests for new behaviour
- [ ] If `skills/repotour/` changed: ran `python scripts/sync_skill.py`
- [ ] `CHANGELOG.md` updated
- [ ] No private names or personal data in code, tests or fixtures (`python scripts/leak_check.py`)
