# Path: mcoc/common/feature_system/resolver.py
# File-Version: 1.0
# File-Id: 420ef9fa-2a92-4114-bf27-b4451d922e9c
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: has_feature
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header


from .registry import FEATURES
from .model import GuildFeatureConfig

def has_feature(ctx, guild_cfg: GuildFeatureConfig, feature_name: str) -> bool:
    """
    Unified entitlement resolver.
    Checks guild flags, user entitlements, roles, and implicit guild owner rights.
    """

    # Unknown feature → deny
    if feature_name not in FEATURES:
        return False

    user_id = ctx.author.id

    # 1. Guild-level flag (explicit enable)
    if guild_cfg.feature_flags.get(feature_name):
        return True

    # 2. Guild owner implicit rights
    if user_id == guild_cfg.owner_id:
        if FEATURES[feature_name]["tier"] in ("free", "guild_owner"):
            return True

    # 3. User-level entitlements (subscriber or guild_owner_plus)
    ent = guild_cfg.entitlements.get(str(user_id))
    if ent:
        if FEATURES[feature_name]["tier"] == "subscriber" and ent.subscriber:
            return True
        if FEATURES[feature_name]["tier"] == "guild_owner_plus" and ent.guild_owner_plus:
            return True

    # 4. Role-based entitlements (Discord Server Subscriptions)
    for role in ctx.author.roles:
        ent = guild_cfg.entitlements.get(f"role:{role.id}")
        if ent:
            if FEATURES[feature_name]["tier"] == "subscriber" and ent.subscriber:
                return True
            if FEATURES[feature_name]["tier"] == "guild_owner_plus" and ent.guild_owner_plus:
                return True

    return False
