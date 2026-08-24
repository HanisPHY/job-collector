"""
Compatibility wrapper for the refactored job_collector package.

DEPRECATED. The LinkedIn lane's real entry point is scripts/main.py, and
scheduled runs go through tasks/run_logged.bat run_newgrad_collector. This file
only exists so an old `python job_collector.py ...` command line still works.

Two things the reorg broke and this bootstrap works around:

  * main.py moved into scripts/, which is not on sys.path when this file is the
    script being run, so scripts/ has to be added;
  * this file is itself called job_collector.py, so its own directory shadows
    the src/job_collector package that main.py imports. Dropping deprecated/
    from sys.path for the duration of the import is the same fix scripts/
    entry points use.
"""

import os
import sys

import paths

sys.path.insert(0, str(paths.ROOT / "scripts"))

_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.remove(_this_dir)
try:
    from main import main
finally:
    sys.path.insert(0, _this_dir)

if __name__ == "__main__":
    sys.stderr.write(
        "warning: job_collector.py is deprecated - use `python scripts\main.py` instead\n")
    main()
