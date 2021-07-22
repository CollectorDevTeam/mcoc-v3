from typing import Literal
import re

from cdtcommon.cdtcommon import CdtCommon

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

_config_structure = {
    "user" : {
        "youtube_id" : None,
    },
    "guild" : {
        "channels": {},
    },
    "channel": {
        "channel_id" : None,
        "channel_name": None,
        "subscriber_role": None,
    }
}

class YouTubeID(commands.Cog):
    """
    Log and store user Youtube Id.
    """


    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=1998837463252134,
            force_registration=True,
        )
        self.config.register_user(**_config_structure["user"])
        self.config.register_guild(**_config_structure["guild"])


    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    #pseudocode command layout
    @commands.group()
    async def ytsubs(self, ctx):
        if not await self.config.user(ctx.author).youtube_id():
            await ctx.send("You aren't registered dummy")
            return
        youtubeid = await self.config.user(ctx.author).youtube_id()
        if youtubeid is not None:
            await ctx.send("{}".format(youtubeid))
        else:
            await ctx.send("Your youtube id is not set.  Get smarter.")

    #yt add id
    # - call confirmation
    @ytsubs.command(name="add")
    async def add_youtube_id(self, ctx, youtubeid:str):
        """Include your youtube userid or your channel url"""
        # need to regex out the url stuff
        youtubeid = regexyt(youtubeid)
        if youtubeid is None:
            await ctx.send("The youtube regex broke, dummy")
            return
        else:
            answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to set {} as your youtube identity?".format(youtubeid))
            if answer:
                await self.config.user(ctx.author).youtube_id.set(youtubeid)
            else:
                await ctx.send("Cancelled")

    #yt delete id
    @ytsubs.command(name="del")
    async def delete_youtube_id(self, ctx):
        """Delete your youtube userid"""
        # need to regex out the url stuff
        answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to delete your youtube identity?")
        if answer:
            # await self.config.user(ctx.author).youtube().id.set(None)
            await self.config.user(ctx.author).clear() # not sure if this is right
            await ctx.send("User data deleted. :sparkles:")

    #guildowner/admin yt addsubrole channel + role for subscribers
    # @ytsubs.command(name="addsubrole")
    # @commands.guildowner_or_permissions(administrator=True)
    # async def add_subrole(self, ctx, youtube_channel:str, subrole: discord.Role):
    #     if subrole in ctx.guild.roles:
    #         youtube_channel = regexyt(youtube_channel)
    #         answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to give the {0.mention} role to subscribers of {1}?".format(subrole, youtube_channel))
    #         if answer:
    #             await self.config.guild(ctx.guild).channel(youtube_channel).set
    #     else:
    #         await ctx.send("The requested role is not available on this server.")

    #guildowner/admin yt deletesubrole channel + role for subscribers




def regexyt(youtubeid:str):
    pattern = '(?:(https?:\/\/)?(www\.)?youtu((\.be)|(be\..{2,5}))\/((user)|(c|channel))\/)'
    regex = re.compile(r'(?:(https?:\/\/)?(www\.)?youtu((\.be)|(be\..{2,5}))\/((user)|(c|channel))\/)')
    yid = regex.match(youtubeid)
    print(yid)
    return yid
