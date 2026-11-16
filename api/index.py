"""Vercel entrypoint. vercel.json rewrites every path here; FastAPI does the routing."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
