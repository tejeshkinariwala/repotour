# Lets you run the tool with `python -m repotour`; it just calls the CLI.
import sys

from repotour.cli import main

if __name__ == "__main__":
    sys.exit(main())
