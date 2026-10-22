"""Web package for Video2ArabicSubs (FastAPI + static frontend).

Ensures the project root is importable no matter how the server is started
(``uvicorn web.main:app``, ``python -m uvicorn``, an IDE run config, ...).
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
