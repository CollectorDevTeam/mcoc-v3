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
        "yt_channels": {},
    },
    "yt_channel_id": {
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
        data = await Embed.create(ctx, title=_TITLE, description="")
        if not await self.config.user(ctx.author).youtube_id():
            data.description = "Your youtube account is not registered." 
            await ctx.send(embed=data)
            return
        youtubeid = await self.config.user(ctx.author).youtube_id()
        if youtubeid is not None:
            data.description = "Your registered Youtube ID is ``{}``".format(youtubeid)
            data.url = "https://www.youtube.com/channel/{}".format(youtubeid)
            await ctx.send(embed=data)
            return

    #yt add id
    # - call confirmation
    @ytsubs.command(name="add")
    async def add_youtube_id(self, ctx, youtubeid:str):
        """Include your youtube userid or your channel url"""
        # need to regex out the url stuff
        data = await Embed.create(ctx, title=_TITLE, description="")
        ycid = regexyt(youtubeid)
        await ctx.send("dbg: youtubeid is {}".format(youtubeid))
        if ycid is None:
            data.description = "Youtube ID could not be extracted."
            await ctx.send(embed=data)
            return
        else:
            answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to set ``{}`` as your youtube identity?".format(ycid))
            if answer:
                await self.config.user(ctx.author).youtube_id.set(ycid)
                data.description = "Youtube ID set as ``{}``".format(ycid)
                await ctx.send(embed=data)
            else:
                data.description = "Youtube ID was not recorded."
                await ctx.send(embed=data)

    #yt delete id
    @ytsubs.command(name="delete", aliases=("rm", "del"))
    async def delete_youtube_id(self, ctx):
        """Delete your youtube userid"""
        data = await Embed.create(ctx, title=_TITLE, description="You are not registered.")
        # need to regex out the url stuff
        if not await self.config.user(ctx.author).youtube_id():
            await ctx.send(embed=data)
        answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to delete your youtube identity?")
        if answer:
            # await self.config.user(ctx.author).youtube().id.set(None)
            await self.config.user(ctx.author).clear() # not sure if this is right
            data.description = "User data deleted."
            await ctx.send(embed=data)
            return

    #guildowner/admin yt addsubrole channel + role for subscribers
    @ytsubs.command(name="addsubrole")
    @commands.guildowner_or_permissions(manage_roles=True)
    async def add_subrole(self, ctx, youtube_channel:str, subrole: discord.Role):
        """Add a subscriber role for your Youtube channel.  """
        data = await Embed.create(ctx, title=_TITLE, description="You are not registered.")
        response = "..."
        ycid = regexyt(youtube_channel)
        
        if subrole not in ctx.guild.roles:
            #check to see if role exists in guild
            response = "The role {0.name} is not available on this guild: {1.name} {1.id}".format(subrole, ctx.guild)
        elif youtube_channel is None:
            response = "The youtube channel {} appears to be invalid.".format(ycid)
        
        if not await self.config.guild(ctx.guild).yt_channels(ycid):
            #check to see if youtube channel is regstered in guild
            question = "This YouTube channel is not registered.\nDo you want to give the role {0.mention} to subscribers "
            if await CdtCommon._get_user_confirmation(self, ctx, question):
                data.description = "Registering Subscriber role {0.mention} for YT channel {1}".format(subrole, ycid)
                status = await ctx.send(embed=data)
                await self.config.guild(ctx.guild).yt_channels.register_custom(ycid, **_config_structure["youtube_channel_id"])
                if await self.config.guild(ctx.guild).yt_channels.ycid():
                    await self.config.guild(ctx.guild).yt_channels.ycid().subscriber_role.set(subrole.id)
                    await self.config.guild(ctx.guild).yt_channels.ycid().channel_id.set(ycid)
                    data.description = "Subscription role {0.mention} registered for {1}.".format(subrole, ycid)
                    await ctx.delete(status)
                    await ctx.send(embed=data)
                else: 
                    data.description = "An error has ocurred the the role was not registered."
                    await ctx.delete(status)
                    await ctx.send(embed=data)
        elif await self.config.guild(ctx.guild).yt_channels(ycid):
            response = "There is an existing role registration for this YouTube Channel."
            xycid = await self.config.guild(ctx.guild).yt_channels(ycid).channel_id()
            xrole = ctx.guild.get_role(await self.config.guild(ctx.guild).yt_channels(ycid).subscriber_role())
            response += "Youtube Channel: www.youtube.com/channel/{0}\nRole for subscribers: {1.mention}".format(xycid, xrole)
            response += "Do you want to replace the existing subscriber role?"
            answer = await CdtCommon._get_user_confirmation(self, ctx, response)
            if answer:
                self.config.guild(ctx.guild).yt_channels(ycid).subscriber_role.set(subrole.id)
                ## possibly call to refresh role assignments
        else:    
            answer = await CdtCommon._get_user_confirmation(self, ctx, "Do you want to give the {0.mention} role to subscribers of {1}?".format(subrole, ycid))
            if answer:           
                await self.config.guild(ctx.guild).ycid.subscriber_role.set(subrole.id)

        data.description = response
        await ctx.send(embed=data)
        return

    #guildowner/admin yt deletesubrole channel + role for subscribers
    @ytsubs.command(name="delsubrole", aliases=("rmsubrole",))
    @commands.guildowner_or_permissions(manage_roles=True)
    async def delete_subrole(self, ctx, youtube_channel:str=None, subrole: discord.Role=None):
        """Delete a registered YouTube subscriber role."""
        if youtube_channel is not None:
            ycid = regexyt(youtube_channel)
            data = Embed.create("CDT Youtube Subscription Removal :sparkles:")
            if await self.config.guild(ctx.guild).ycid():
                question = "Do you want to remove the YouTube channel registration?"
                answer = await CdtCommon._get_user_confirmation(question)
                if answer:
                    await self.config.guild(ctx.guild).ycid().clear()
                    response = "Registration deleted."
                else:
                    response = "Registration deletion aborted."
                data.description=response
                await ctx.send(embed=data)
                return




def regexyt(youtubeid:str):
    pattern = '(?:(https?:\/\/)?(www\.)?youtu((\.be)|(be\..{2,5}))\/((user)|(c|channel))\/)'
    # regex = re.compile(r'(?:(https?:\/\/)?(www\.)?youtu((\.be)|(be\..{2,5}))\/((user)|(c|channel))\/)')
    ycid = re.sub(pattern, '', youtubeid)    
    # ycid = regex.sub(youtubeid, '')
    print(ycid)
    return ycid
