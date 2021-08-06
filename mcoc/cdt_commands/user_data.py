import datetime
from logging import exception
import random
from redbot.core.utils import menus
from typing import Optional
import discord
from dateutil.parser import parse as date_parse
from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdt_core import CDT
from ..exceptions import MODOKException
import json
from ..config_structure import config_structure

PROFILE_TITLE="CollectorVerse User Profile:sparkles:"
PROFILE_FOOTER="CollectorVers User Profile | CollectorDevTeam"

AFFIRMATIVE = ["It is done.", "As you wish, peasant.", "Fine.", "This is what the peons always request."]



class ProfileData(MixinMeta, metaclass=CompositeMetaClass):
    """MCOC Profile commands"""

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_user(**config_structure["default_user"])


    @commands.group(name="profile")
    @CDT.is_collectordevteam()
    async def profilegroup(self, ctx: Context):
        """MCOC Profile commands"""

        if ctx.invoked_subcommand is None:
            await self.display_user_profile(ctx, ctx.author)

    # @profilegroup.command(name="create")
    # async def profile_create(self, ctx: Context):
    #     """Register MCOC Profile"""
    #     if ctx.author.id in await self.config.all_users():
    #         await ctx.send("You already have a CollectorVerse profile")
    #     else:
    #         if ctx.author.id not in await self.config.all_users():
    #             answer = ctx.send("You do not have a CollectorVerse Profile registered.  Would you like to register?")
    #             if answer:
    #                 self.actual_create(ctx)

    @profilegroup.command("showall", hidden=True)
    @CDT.is_collectorsupportteam()
    async def profile_read_all(self, ctx: Context, user: Optional[discord.User]):
        await ctx.send("reading user profile")
        if user is None:
            user = ctx.author
        settings = await self.config.user(user).settings.all()
        profile = await self.config.user(user).profile.all()

        await ctx.send("```{}```".format(json.dumps(settings)))
        await ctx.send("```{}```".format(json.dumps(profile)))


    @profilegroup.command("show")
    async def profile_read(self, ctx: Context, user: Optional[discord.User]):
        """Read MCOC Profile"""
        if not user:
            user = ctx.author
        await self.display_user_profile(ctx, user)
            

    # async def show_profile(self, ctx: Context, user: discord.User):
    #     """Show user profile.
    #     Retrieve user settings from profile.
    #     Build profile embed.
    #     Send profile embed.

    #     Args:
    #         ctx ([type]): [description]
    #         user (discord.User): [description]
    #     """
    #     if user is None:
    #         user = ctx.author
    #     if user.id not in await self.config.users():
    #         if user == ctx.author:
    #             await self.config.register_user(**self.default_user_profile)
    #         else:
    #             # should be an exception but I dont' have a handle on that yet
    #             await ctx.send("User has not registered for a profile.")
    #     else:
    #         await self.display_user_profile(ctx, user)


    async def display_user_profile(self, ctx: Context, user: discord.User):
        """Get user profile from config.
        Honor User settings from profile.settings()
        Create Embed, send embed.

        Args:
            ctx ([type]): [description]
            user (discord.User): [description]
        """

        async with self.config.user(user).profile() as profile:
            roster_pages = []
            data = await CDT.create_embed(ctx, title=PROFILE_TITLE, footer_text=PROFILE_FOOTER)
            if profile["ingame"] is not None:
                data.add_field(name="In-Game Name", value=profile["ingame"])
            if profile["started"] is not None:
                since = date_parse(profile["started"])
                days_since = (datetime.datetime.utcnow()-since).days
                data.add_field(name='Started playing: {}'.format(since.date()), value="Playing for {} days!"
                .format(days_since))

            if len(profile["roster_screenshots"])>0:
                for ss in profile["roster_screenshots"]:
                      data.image(ss)
                      p = data
                      roster_pages.append(p)
            else:
                roster_pages.append(data)

            await menus.menu(ctx,pages=roster_pages, controls=CDT.get_controls(len(roster_pages)))
            
    @profilegroup.group(name="update", aliases=("set",))
    async def profile_update(self, ctx: Context):
        """Update MCOC Profile"""

    @profile_update.command(name="ingame")
    async def profile_ingame(self, ctx: Context, ingame: str):
        await self.config.user(ctx.author).profile.ingame.set(ingame)
        await self.follow_up(ctx)
            
    @profile_update.command(name="started")
    async def profile_ingame(self, ctx: Context, date):
        if isinstance(date_parse(date), datetime.datetime):
            await self.config.user(ctx.author).profile.started.set(date)
            await self.follow_up(ctx)
            




    async def follow_up(self, ctx: Context):
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if can_react:
            await ctx.message.add_reaction("☑️")
        else:
            await ctx.send(random.choice(AFFIRMATIVE))

        


    @profilegroup.command(name="delete")
    async def profile_delete(self, ctx: Context): 
        """Delete MCOC Profile"""
        answer = CDT.confirm(self, ctx, "Do you want to delete your MCOC profile?")
        if answer:
            await self.config.user(ctx.author).profile.clear()
            await self.follow_up(ctx)


    
 