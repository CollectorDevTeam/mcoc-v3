# Path: mcoc/common/__init__.py
# File-Version: 1.0
# File-Id: 6a387084-2b1f-4aba-b9a4-cef061a110b0
# Purpose: Provide a unified namespace for all common MCOC systems.
# Public-API: Core
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
"""
Unified namespace for all common MCOC systems.

This package intentionally avoids eager imports of Discord UI components so the
backend data layer can be imported in non-bot environments during development.
"""

from . import helpers as _helpers
from .feature_system import CDTEntitlements

try:
    from mcoc.common.components.componentsV2 import CDTEmbed, CDTConfirm, CDTPagesMenu
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    CDTEmbed = None
    CDTConfirm = None
    CDTPagesMenu = None


class Core:
    """
    Unified namespace for common systems.
    Automatically exposes:
      Core.Embed
      Core.Confirm
      Core.PagesMenu
      Core.Helpers.<module>
    """
    Embed = CDTEmbed
    Confirm = CDTConfirm
    PagesMenu = CDTPagesMenu
    Entitlements = CDTEntitlements
    Helpers = _helpers


__all__ = ["Core", "helpers"]
