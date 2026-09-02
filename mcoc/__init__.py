# Path: mcoc/__init__.py
# File-Version: 1.0
# File-Id: ff78460a-1733-49d5-8640-856abb853312
# Purpose: Initialize the MCOC package and provide the public setup function.
# Public-API: list of exported functions/classes (comma separated)
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from .core import setup  # keep core.py as the implementation
__all__ = ("setup",)
