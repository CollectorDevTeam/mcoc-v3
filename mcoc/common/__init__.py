"""
Unified namespace for all common MCOC systems.
"""

from mcoc.common.componentsV2 import CDTEmbed, CDTConfirm, CDTPagesMenu
from mcoc.common.feature_system import CDTEntitlements
from mcoc.common.helpers import CDTHelpers

class Core:
    """
    Unified namespace for common systems.
    Automatically exposes:
      Core.Embed
      Core.Confirm
      Core.PagesMenu
      Core.Entitlements
      Core.Helpers.<module>
    """
    Embed = CDTEmbed
    Confirm = CDTConfirm
    PagesMenu = CDTPagesMenu
    Entitlements = CDTEntitlements
    Helpers = CDTHelpers


__all__ = ["Core"]
