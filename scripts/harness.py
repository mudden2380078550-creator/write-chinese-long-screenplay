"""Portable source checkout launcher; no machine-specific Python paths."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from narrative_harness.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
