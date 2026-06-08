"""Module entry point — ``python -m imdr.research.auth ...``."""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
