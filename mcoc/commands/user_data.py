from logging import exception
from redbot.core.utils import menus
from typing import Optional
import discord
from .abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass, CDT, mcocgroup
from ..exceptions import MODOKException

PROFILE_TITLE="CollectorVerse User Profile:sparkles:"
PROFILE_FOOTER="CollectorVers User Profile | CollectorDevTeam"


class ProfileData(MixinMeta, metaclass=CompositeMetaClass):
    """MCOC Profile commands"""

    @mcocgroup.group(name="profile")
    @CDT.is_collectordevteam()
    async def profilegroup(self, ctx: Context):
        """MCOC Profile commands"""
        pass

    @profilegroup.command(name="create")
    async def profile_create(self, ctx: Context):
        """Register MCOC Profile"""
        # if not user:
        #     user = ctx.author
        if ctx.author.id not in await self.config.users():
            await self.config.register_user(**self.default_user_profile) 

    @profilegroup.command("show")
    async def profile_read(self, ctx: Context, user: Optional[discord.User]):
        """Read MCOC Profile"""
        if not user:
            user = ctx.author
        if user.id not in await self.config.users() and user == ctx.author:
            answer = await CDT.confirm("User profile for ``{0.name}`` not found.\nDo you want to create a profile?".format(user))
            

    async def show_profile(self, ctx: Context, user: discord.User):
        """Show user profile.
        Retrieve user settings from profile.
        Build profile embed.
        Send profile embed.

        Args:
            ctx ([type]): [description]
            user (discord.User): [description]
        """
        if user is None:
            user = ctx.author
        if user.id not in await self.config.users():
            if user == ctx.author:
                await self.config.register_user(**self.default_user_profile)
            else:
                # should be an exception but I dont' have a handle on that yet
                await ctx.send("User has not registered for a profile.")
        else:
            await self.display_user_profile(ctx, user)


    async def display_user_profile(self, ctx: Context, user: discord.User):
        """Get user profile from config.
        Honor User settings from profile.settings()
        Create Embed, send embed.

        Args:
            ctx ([type]): [description]
            user (discord.User): [description]
        """

        with self.config.users(user.id).profile() as profile:
            roster_pages = []
            data = CDT.create_embed(title=PROFILE_TITLE, footer_text=PROFILE_FOOTER)
            if profile["ingame"] is not None:
                data.add_field(name="In-Game Name", value=profile["ingame"])
            if len(profile["roster_screenshots"])>0:
                for ss in profile["roster_screenshots"]:
                      data.image(ss)
                      p = data
                      roster_pages.append(p)
            else:
                roster_pages.append(data)

            await menus.menu(ctx,pages=roster_pages)
            

        




    async def profile_update(self, ctx: Context):
        """Update MCOC Profile"""

    async def profile_delete(self, ctx: Context): 
        """Delete MCOC Profile"""
        answer = CDT.confirm("Do you want to delete your MCOC profile?")
        if answer:
            await self.config.users(ctx.author).profile.clear()


    
 