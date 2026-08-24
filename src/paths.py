"""
Single source of truth for where data/config/state files live.

ROOT is derived from this file's own location, not the caller's CWD or
__file__, so `import paths` resolves identically whether it's a scheduled
task launched from tasks/, a script run from scripts/, or a package deep
under src/.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
