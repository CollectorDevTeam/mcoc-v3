# mcoc/common/feature_system/registry.py

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
    "analytics": {
        "tier": "subscriber",
        "description": "Prestige trends, roster analytics, alliance dashboards."
    },
}
