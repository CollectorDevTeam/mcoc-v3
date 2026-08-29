# mcoc/common/feature_system/model.py

from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class UserEntitlement:
    subscriber: bool = False
    guild_owner_plus: bool = False
    expires_at: Optional[str] = None
    subscription_id: Optional[str] = None

@dataclass
class GuildFeatureConfig:
    guild_id: int
    owner_id: int
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    entitlements: Dict[str, UserEntitlement] = field(default_factory=dict)
    audit_log: list = field(default_factory=list)

    def grant_user(self, user_id: int, **kwargs):
        ent = self.entitlements.get(str(user_id), UserEntitlement())
        for k, v in kwargs.items():
            setattr(ent, k, v)
        self.entitlements[str(user_id)] = ent

    def revoke_user(self, user_id: int):
        self.entitlements.pop(str(user_id), None)

    def set_flag(self, feature: str, enabled: bool):
        self.feature_flags[feature] = enabled
