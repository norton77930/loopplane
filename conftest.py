"""Repository-wide pytest bootstrap."""

from pathlib import Path

# pytest does not recursively create the parent of a configured basetemp.
Path("tmp").mkdir(exist_ok=True)
