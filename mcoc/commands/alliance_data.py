from cdtcommon.abc.cdtcheck import CdtCheck
from alliance.alliance import officer_check
from discord.ext.commands.core import has_guild_permissions
from discord.ext.commands.errors import ExpectedClosingQuoteError
from redbot.core import commands
from redbot.core.commands import guild_only
# from discord.ext.commands.core import guild_only
from redbot.core.bot import Red
from redbot.core.config import Config

from ..abc import CompositeMetaClass, MixinMeta, alliancegroup
from ..cdtcore import CDT

import discord
from typing import Union, Optional


GUILDOWNER_ONLY = "Only guild owners or guild administrators may execute this command."
OFFICER_ONLY = "Only Alliance Officers may set Alliance properties."


class AllianceData(MixinMeta, metaclass=CompositeMetaClass):
    """Alliance Data by CollectorDevTeam"""

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




    @alliancegroup.command(name="create")
    @guild_only()
    @commands.guildowner_or_permissions(admin=True)
    async def alliance_create(self, ctx, user: Optional[discord.User]):
        """Create alliance"""


    @alliancegroup.command(name="read")
    async def read_alliance(self, ctx, user: Optional[discord.User]):
        """Display alliance card"""


    @alliancegroup.group(name="update", aliases=("set"))
    async def alliance_update(self, ctx):
        """Update alliance settings"""
        aid = await AllianceData.find_alliance_id(self, ctx, ctx.author)
        officerTest = await AllianceData.alliance_officer_check(self, ctx,aid, ctx.author)
        if not officerTest:
            data = await CDT.create_embed(ctx, description=OFFICER_ONLY)
            await ctx.send(embed=data)

    @alliancegroup.command(name="delete")
    async def alliance_delete(self, ctx):
        """Delete alliance registration"""


