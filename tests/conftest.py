"""Shared pytest configuration."""

from __future__ import annotations

import os
from pathlib import Path


_NUMBA_CACHE_DIR = Path(os.environ.get("NUMBA_CACHE_DIR", "/private/tmp/mariachi_music_numba_cache"))
_NUMBA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(_NUMBA_CACHE_DIR))
