"""Tiny invented server used by the mixed fixture."""

from src.core.engine import Engine


def _parse(raw):
    return raw.strip()


def serve(raw):
    return Engine().run(_parse(raw))
