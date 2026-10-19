"""Where headless Chrome lives: $CHROME, else the macOS default."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def chrome_path() -> str:
    return os.environ.get("CHROME", DEFAULT_CHROME)


def chrome_available() -> bool:
    return Path(chrome_path()).exists()
