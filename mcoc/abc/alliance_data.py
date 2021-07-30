from cdtcommon.abc.cdtcheck import CdtCheck
from alliance.alliance import officer_check
from discord.ext.commands.core import has_guild_permissions
from discord.ext.commands.errors import ExpectedClosingQuoteError
from redbot.core import commands
from redbot.core.commands import guild_only
# from discord.ext.commands.core import guild_only
from redbot.core.bot import Red
from redbot.core.config import Config
from mcoc.abc.abc import MCOCMixinMeta
from mcoc.abc.mixin import alliancecommands
from cdtcommon.cdtcommon import CDT

import discord
from typing import Union, Optional



_config_structure = {
    "global": {
        "alliances": {},
        "family": {},
    },
    "alliance": {
        "guild": None,  # int guild id
        "name": "Default Name",  # str
        "tag": "ABCDE",  # str
        "leader" : None,
        "officers": None,  # int For the role id
        "members": None,  # int For the role id
        "bg1": None,
        "bg2": None,
        "bg3": None,
        "poster": None,  # str An image link, NOTE use aiohttp for this
        "summary": None,  # str The summary of the alliance
        "registered": False,
        "creation_date": None,
        "invite_url": None,
    }
}

GUILDOWNER_ONLY = "Only guild owners or guild administrators may execute this command."
OFFICER_ONLY = "Only Alliance Officers may set Alliance properties."


class AllianceData(MCOCMixinMeta):
    """Alliance Data by CollectorDevTeam"""


    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 544974305445019651, True)
        self.config.register_global(
            **_config_structure["global"]
        )

    async def find_alliance_id(self, ctx, user: Optional[discord.User]):
        """Find user in  guild"""
        if user is None:
            user = ctx.author

        async with self.config.alliances() as alliances:
            for aid in alliances.keys():
                guild = self.bot.get_guild(alliances[aid]["guild"])
                members = CDT.list_role_members(self, ctx, guild, guild.get_role(aid))
                if user in members:
                    return aid
            return None
        
    async def alliance_officer_check(self, ctx, alliance_id, user: Optional[discord.User]):
        """Check user in alliance Officers"""
        if user is None:
            user = ctx.author
        
        guild = self.bot.get_guild(self.config.alliances(alliance_id).guild())
        if guild is None:
            ctx.send("No guild in registration. Big problem")
        else:
            oid = self.config.alliances(alliance_id).officers()
            officers = guild.get_role(oid)
            if officers is None:
                ctx.send("Alliance has no valid officers role. Big problem")
            else:
                if user in CDT.list_role_members(self, ctx, guild, officers):
                    return True
            leader = self.config.alliances(alliance_id).leader()




    @alliancecommands.command()
    @guild_only()
    @commands.guildowner_or_permissions(admin=True)
    async def create_alliance(self, ctx, user: Optional[discord.User]):
        """Create alliance"""


    @alliancecommands.command()
    async def read_alliance(self, ctx, user: Optional[discord.User]):
        """Display alliance card"""


    @alliancecommands.group(name="update", aliases=("set"))
    async def update_alliance(self, ctx):
        """Update alliance settings"""
        aid = await AllianceData.find_alliance_id(self, ctx, ctx.author)
        officerTest = await AllianceData.alliance_officer_check(self, ctx,aid, ctx.author)
        if not officerTest:
            data = await CDT.create_embed(ctx, description=OFFICER_ONLY)
            await ctx.send(embed=data)


        # alliance = await AllianceData.find_alliance_id(self, ctx, ctx.guild, ctx.author)
        # if alliance is None:
        #     alliance = await AllianceData.find_guild(self, ctx, ctx.author)
        # if alliance is None:
        #     ctx.send("User not found in any registered alliance.")
        #     return
        # else:
        #     async with self.config.guild()
