# mcoc/common/feature_system/audit.py

from datetime import datetime

def log_action(guild_cfg, actor_id: int, action: str, detail: str):
    guild_cfg.audit_log.append({
        "actor": actor_id,
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat()
    })
