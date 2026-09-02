# Path: mcoc/common/helpers/__init__.py
# File-Version: 1.0
# File-Id: f80d2b28-91b5-4444-9f9c-70f1aa670512
# Purpose: Public helper API for frontends (userdata, account, roster, champions)
# Public-API: get_user_manager, UserDataManager, Account helpers, Champion, champion_from_dict, useraccount_from_userdata
# Last-Modified: 2026-09-01

from . import account, alliance, champions, roster, types, userdata
from .userdata import get_user_manager, UserDataManager
from .account import (
    user_has_consented,
    enroll_command_handler,
    handle_consent_response,
    link_account,
    unlink_account,
    get_profile,
    set_profile_field,
)
from .roster import parse_roster_entries_from_input, build_roster_pages, schedule_persist_user_prestige
from .types import (
    Champion,
    champion_from_dict,
    UserAccount,
    useraccount_from_userdata,
    userdata_from_useraccount,
)

__all__ = [
    "account",
    "alliance",
    "champions",
    "roster",
    "types",
    "userdata",
    "UserDataManager",
    "get_user_manager",
    "user_has_consented",
    "handle_consent_response",
    "enroll_command_handler",
    "link_account",
    "unlink_account",
    "get_profile",
    "set_profile_field",
    "parse_roster_entries_from_input",
    "build_roster_pages",
    "schedule_persist_user_prestige",
    "Champion",
    "champion_from_dict",
    "UserAccount",
    "useraccount_from_userdata",
    "userdata_from_useraccount",
]
