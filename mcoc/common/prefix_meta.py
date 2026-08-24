# mcoc/common/account_meta.py
ALLOWED_PROFILE_FIELDS = {
    "mcoc_name": "In-game player name",
    "mcoc_id": "In-game numeric id",
    "website": "Personal website or profile URL",
    "invite": "Alliance invite link or code",
    "timezone": "Timezone (e.g., America/Chicago)",
    "alliance": "Alliance name",
    "job": "Short job/role text",
}

ACCOUNT_GROUP_HELP = {
    "account": "Account commands: info, set, link, unlink, delete, privacy",
    "account_set": "Set a profile field. Usage: ///mcoc account set <field> <value>",
    "account_link": "Link your Discord account to an in-game account. Usage: ///mcoc account link <mcoc_id>",
    "account_unlink": "Unlink your Discord account from an in-game account. Usage: ///mcoc account unlink",
    "account_delete": "Delete your user data file. Usage: ///mcoc account delete",
    "account_privacy": "Manage privacy settings. Usage: ///mcoc account privacy <subcommand>",
    "account_privacy_mode": "Set privacy mode. Usage: ///mcoc account privacy mode <private|guild|alliance|public>",
    "account_privacy_allow_guild": "Allow sharing with a specific guild. Usage: ///mcoc account privacy allow_guild <guild_id>",
    "account_privacy_revoke_guild": "Revoke sharing with a specific guild. Usage: ///mcoc account privacy revoke_guild <guild_id>",
}

ALLOWED_ROSTER_FIELDS = {
    "name": "Character name",
    "level": "Character level",
    "rank": "Character rank",
    "stars": "Number of stars",
    "class": "Character class",
}

ROSTER_GROUP_HELP = {
    "roster": "Commands related to managing your character roster",
    "roster_add": "Commands related to adding characters to your roster",
    "roster_remove": "Commands related to removing characters from your roster",
    "roster_update": "Commands related to updating characters in your roster",
    "roster_list": "Commands related to listing characters in your roster",
    "roster_export": "Commands related to exporting characters from your roster",
    "roster_import": "Commands related to importing characters into your roster",
    "roster_clear": "Commands related to clearing your roster",
}

ALLIANCE_HELP = {
    "alliance": "Commands related to managing your alliance",
    "alliance_info": "View alliance information",
    "alliance_invite": "Invite a member to the alliance",
    "alliance_kick": "Kick a member from the alliance",
    "alliance_promote": "Promote a member within the alliance",
    "alliance_demote": "Demote a member within the alliance",
    "alliance_settings": "Manage alliance settings",
}

ALLIANCE_PROFILE_FIELDS = {
    "name": "Alliance name",
    "tag": "Alliance tag",
    "leader": "Alliance leader",
    "members": "Number of members",
    "level": "Alliance level",
    "description": "Alliance description",
}