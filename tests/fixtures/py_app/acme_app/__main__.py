"""Entry point: `python -m acme_app`."""
import sys

from acme_app.commands import dispatch


def main() -> int:
    dispatch(sys.argv[1] if len(sys.argv) > 1 else "list", sys.argv[2:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
