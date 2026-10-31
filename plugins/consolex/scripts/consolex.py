#!/usr/bin/env python3
"""Codex adapter entrypoint; the builder includes its shared modules."""
import os
from pathlib import Path
import runpy
os.environ['CONSOLEX_RUNTIME'] = 'codex'
_runtime = Path(__file__).with_name('runtime.py')
if not _runtime.is_file():
    _runtime = Path(__file__).resolve().parents[4] / 'coding_agents' / 'runtime.py'
runpy.run_path(str(_runtime), run_name='__main__')
