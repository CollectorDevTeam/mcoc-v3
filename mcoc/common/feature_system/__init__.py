# mcoc/common/feature_system/__init__.py
"""Feature system package for MCOC."""
from .model import UserEntitlement, GuildFeatureConfig
from .resolver import has_feature
from .registry import FEATURES

class CDTEntitlements:
    pass
    __all__ = ["UserEntitlement", "GuildFeatureConfig", "has_feature", "FEATURES"]