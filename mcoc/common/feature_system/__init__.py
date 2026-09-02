# Path: mcoc/common/feature_system/__init__.py
# File-Version: 1.0
# File-Id: 5f7bf9b4-3a96-4ad0-8b63-d6803f6d4a56
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: 
# Internal: CDTEntitlements
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
from .model import UserEntitlement, GuildFeatureConfig
from .resolver import has_feature
from .registry import FEATURES
from .audit import log_action

class CDTEntitlements:
    UserEntitlement = UserEntitlement
    GuildFeatureConfig = GuildFeatureConfig
    has_feature = has_feature
    FEATURES = FEATURES
    log_action = log_action
