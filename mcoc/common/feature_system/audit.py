# Path: mcoc/common/feature_system/audit.py
# File-Version: 1.0
# File-Id: c9b538e5-020c-4b0b-8e5d-49a9590168e7
# Purpose: Provide audit logging functionality for feature system actions.
# Public-API: log_action
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from datetime import datetime

def log_action(guild_cfg, actor_id: int, action: str, detail: str):
    guild_cfg.audit_log.append({
        "actor": actor_id,
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat()
    })
