# Path: mcoc/common/account.py
# File-Version: 1.0
# File-Id: 2fefecb1-38af-44ec-a7bb-cb610f9f38b7
# Purpose: Backward-compatible account helper re-export module.
# Public-API: account helper functions used by prefix command modules.
# Last-Modified: 2026-09-01
"""Compatibility shim for legacy imports.

Historically, callers imported account helpers from mcoc.common.account.
The canonical implementation now lives in mcoc.common.helpers.account.
"""

from mcoc.common.helpers.account import (
    ALLOWED_PROFILE_FIELDS,
    FIELD_CANONICAL,
    POLICY_METADATA,
    delete_user_profile,
    enroll_command_handler,
    get_profile,
    get_profile_settings,
    handle_consent_response,
    link_account,
    persist_profile,
    set_profile_field,
    unlink_account,
    user_has_consented,
    validate_profile_field,
)

__all__ = [
    "ALLOWED_PROFILE_FIELDS",
    "FIELD_CANONICAL",
    "POLICY_METADATA",
    "validate_profile_field",
    "get_profile_settings",
    "get_profile",
    "set_profile_field",
    "persist_profile",
    "delete_user_profile",
    "link_account",
    "unlink_account",
    "user_has_consented",
    "enroll_command_handler",
    "handle_consent_response",
]
