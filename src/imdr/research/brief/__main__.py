"""Allow ``python -m imdr.research.brief ...``."""
from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
