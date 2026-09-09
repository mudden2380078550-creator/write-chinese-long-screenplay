"""Installed skill launcher with a portable bundled core."""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
vendor = here / '_vendor'
source = here.parents[2] / 'src'
sys.path.insert(0, str(vendor if vendor.is_dir() else source))
from narrative_harness.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
