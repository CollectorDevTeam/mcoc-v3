from typing import Literal
import re

from cdtcommon.cdtcommon import CdtCommon
from cdtcommon.cdtembed import Embed

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

_TITLE="CDT Youtube Identity System :sparkles:"

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
        data = Embed.create(title=_TITLE)
        if not await self.config.user(ctx.author).youtube_id():
            data.description("Your youtube account is not registered.")
            await ctx.send(data)
            return
        youtubeid = await self.config.user(ctx.author).youtube_id()
        if youtubeid is not None:
            data.description("Your registered Youtube ID is ``{}``".format(youtubeid))
            data.url("https://www.youtube.com/channel/{}".format(youtubeid))
            await ctx.send(data)
            return

    #yt add id
    # - call confirmation
    @ytsubs.command(name="add")
    async def add_youtube_id(self, ctx, youtubeid:str):
        """Include your youtube userid or your channel url"""
        # need to regex out the url stuff
        data = Embed.create(title=_TITLE)
        youtubeid = regexyt(youtubeid)
        await ctx.send("dbg: youtubeid is {}".format(youtubeid))
        if youtubeid is None:
            data.description("Youtube ID could not be extracted.")
            await ctx.send(embed=data)
            return
        else:
            answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to set ``{}`` as your youtube identity?".format(youtubeid))
            if answer:
                await self.config.user(ctx.author).youtube_id.set(youtubeid)
                data.description("Youtube ID set as ``{}``".format(youtubeid))
                await ctx.send(data)
            else:
                data.description("Youtube ID was not recorded.")
                await ctx.send(data)

    #yt delete id
    @ytsubs.command(name="delete", aliases=("rm", "del"))
    async def delete_youtube_id(self, ctx):
        """Delete your youtube userid"""
        data = Embed.create(title=_TITLE)
        # need to regex out the url stuff
        if not await self.config.user(ctx.author).youtube_id():
            data.description("You are not registered.")
            await ctx.send(embed=data)
        answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to delete your youtube identity?")
        if answer:
            # await self.config.user(ctx.author).youtube().id.set(None)
            await self.config.user(ctx.author).clear() # not sure if this is right
            data.description("User data deleted.")
            await ctx.send(embed=data)
            return

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
    # regex = re.compile(r'(?:(https?:\/\/)?(www\.)?youtu((\.be)|(be\..{2,5}))\/((user)|(c|channel))\/)')
    yid = re.sub(pattern, '', youtubeid)    
    # yid = regex.sub(youtubeid, '')
    print(yid)
    return yid
