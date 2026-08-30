from .model import UserEntitlement, GuildFeatureConfig
from .resolver import has_feature
from .registry import FEATURES

class CDTEntitlements:
    UserEntitlement = UserEntitlement
    GuildFeatureConfig = GuildFeatureConfig
    has_feature = has_feature
    FEATURES = FEATURES

__all__ = ["CDTEntitlements"]
