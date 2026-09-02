# Path: mcoc/slash/__init__.py
# File-Version: 1.0
# File-Id: c91f04b3-2841-44aa-8fed-bd227d414364
# Purpose: Provide slash command handler for MCOC commands.
# Public-API: SlashCommandManager
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from .core import MCOCSlash

# Keep package import-neutral; individual modules expose async setup(bot).
__all__ = ["MCOCSlash"]
