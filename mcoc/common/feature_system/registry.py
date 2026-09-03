# Path: mcoc/common/feature_system/registry.py
# File-Version: 1.0
# File-Id: dd9cbd79-b0c6-4169-8a8a-f78b5b7d658d
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: FEATURES
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header


FEATURES = {
    "basic_roster": {
        "tier": "free",
        "description": "Basic roster commands: add/remove/update/list.",
    },
    "basic_alliance": {
        "tier": "free",
        "description": "One alliance per guild (guild owner only)."
    },
    "multi_alliance": {
        "tier": "guild_owner_plus",
        "description": "Create and manage multiple alliances."
    },
    "advanced_roster_export": {
        "tier": "subscriber",
        "description": "CSV/XLSX export with advanced fields."
    },
    "priority_sync": {
        "tier": "subscriber",
        "description": "Faster cache sync windows and on-demand sync."
    },
    "champion_admin": {
        "tier": "guild_owner_plus",
        "description": "Manage champion aliases, shortnames, and metadata overrides."
    },
    "analytics": {
        "tier": "subscriber",
        "description": "Prestige trends, roster analytics, alliance dashboards."
    },
}
