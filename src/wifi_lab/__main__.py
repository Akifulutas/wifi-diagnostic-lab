"""Entry point for python -m wifi_lab."""

from __future__ import annotations

import sys
from wifi_lab.cli import main

if __name__ == "__main__":
    sys.exit(main())
