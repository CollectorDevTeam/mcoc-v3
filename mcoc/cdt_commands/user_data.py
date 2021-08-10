import datetime
from logging import exception
import random

from typing import Optional
import discord
from dateutil.parser import parse as date_parse
from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdt_core import CDT
from redbot.core.utils.menus import menu, next_page, prev_page, close_menu
from ..exceptions import MODOKException
import json
from ..config_structure import config_structure

PROFILE_TITLE="CollectorVerse User Profile :sparkles:"
PROFILE_FOOTER="CollectorVers User Profile | CollectorDevTeam"

AFFIRMATIVE = ["It is done.", "As you wish, peasant.", "Fine.", "This is what the peons always request."]



class ProfileData(MixinMeta, metaclass=CompositeMetaClass):
    """MCOC Profile commands"""

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_user(**config_structure["default_user"])


    @commands.group(name="profile", invoke_without_command=True)
    @CDT.is_collectordevteam()
    async def profilegroup(self, ctx: Context, user: Optional [discord.User]):
        """MCOC Profile commands"""
        if ctx.invoked_subcommand is None:
            await self.display_user_profile(ctx, user)
            return
        else:
            pass

    @profilegroup.command("showall", hidden=True)
    @CDT.is_collectorsupportteam()
    async def profile_read_all(self, ctx: Context, user: Optional[discord.User]):
        await ctx.send("reading user profile")
        if user is None:
            user = ctx.author
        settings = await self.config.user(user).settings.all()
        profile = await self.config.user(user).profile.all()

        await ctx.send("settings:\n```json\n{}```".format(json.dumps(settings, indent=4)))
        await ctx.send("profile:\n```json\n{}```".format(json.dumps(profile, indent=4)))


    @profilegroup.command("show")
    async def profile_read(self, ctx: Context, user: Optional[discord.User]):
        """Read MCOC Profile"""
        if not user:
            user = ctx.author
        await self.display_user_profile(ctx, user)
            


    async def display_user_profile(self, ctx: Context, user: discord.User):
        """Get user profile from config.
        Honor User settings from profile.settings()
        Create Embed, send embed.

        Args:
            ctx ([type]): [description]
            user (discord.User): [description]
        """
        if user is None:
            user = ctx.author

        regionrole, timezonerole = await self.get_user_timezone(ctx, user)
        # if user.id not in await self.config.all_users():
        #     ctx.send("No profile found")
        #     return
        async with self.config.user(user).profile() as profile:
            profile_pages = []
            mastery_pages = []
            since = None 
            days_since = None
            if profile["started"] is not None:
                since = date_parse(profile["started"])
                days_since = (datetime.datetime.utcnow()-since).days
            

            data = await CDT.create_embed(ctx, title=PROFILE_TITLE, footer_text=PROFILE_FOOTER)
            if profile["ingame"] is not None:
                data.add_field(name="In-Game Name", value=profile["ingame"], inline=False)
            if since is not None:
                data.add_field(name='Started playing: {}'.format(since.date()), value="Playing for {} days!"
                .format(days_since), inline=False)

            if regionrole is not None:
                data.add_field(name="Region", value=regionrole.name, inline=True)
            if timezonerole is not None:
                data.add_field(name="Timezone", value=timezonerole.name, inline=True)
            profile_pages.append(data)

            umcoc_progression = await self.get_user_progression(ctx, user)
            data.description = umcoc_progression
            # if umcoc_progression is not None:
            #     data.add_field(name="UMCOC:tm: verified progression", value=umcoc_progression)
            for ss in profile["roster_ss"]:
                data = await CDT.create_embed(ctx, title="Roster Screenshots :sparkles:", footer_text=PROFILE_FOOTER, image=ss)
                profile_pages.append(data)

            for sskey in ("offense", "defense", "utility", "collage"):
                if profile[sskey] is not None:
                    sscolor = CDT.MasteryColors[sskey]
                    data = await CDT.create_embed(ctx, title="{0} Mastery Rig :sparkles:".format(sskey.title()), footer_text=PROFILE_FOOTER, image=profile[sskey])
                    # data.set_image(profile[sskey])
                    data.color=sscolor
                    profile_pages.append(data)
        

        # Until I map out more complex controls, I will just append Mastery to the end of Roster pages
        if len(profile_pages) > 1:
            await menu(ctx, profile_pages, controls=CDT.get_controls(0))
        elif len(profile_pages)==1:
            await ctx.send(embed=profile_pages[0])
        return


    async def get_user_progression(self, ctx: Context, user: discord.User):
        """[summary]

        Args:
            ctx (Context): [description]
            user (discord.User): [description]

        Returns:
            [string]: [Comma separated join of UMCOC approved titles]
        """
        LEGEND = 383866961135665153
        ABYSS = 671511551982829578
        ACT6100 = 706576137857400912
        THRONEBREAKER = 758868876749570068
        LOL100 = 390358067465682960
        LOL = 383864813316734977
        CAVALIER = 555589501725048844
        UNCOLLECTED = 390268311046455316
        PROGRESSION = (LEGEND, ABYSS, ACT6100, THRONEBREAKER, LOL100, LOL, CAVALIER, UNCOLLECTED)
        umcoc = self.bot.get_guild(378035654736609280)
        member = await umcoc.fetch_member(user.id)
        if member is None:
            print(member.id)
            return None
        
        verfied=[] 
        for r in PROGRESSION:
            role = umcoc.get_role(r)
            if role in member.roles:
                verfied.append(role.name)
        joined = ", ".join(verfied)
        return "__UMCOC:tm: Verified__:\n"+joined

    async def get_user_timezone(self, ctx: Context, user: discord.User):
        umcoc = self.bot.get_guild(378035654736609280)
        if user is None:
            user = ctx.author
        uid = user.id
        member = await umcoc.fetch_member(uid)
        if member is None:
            print(member.id)
            return None
        regionrole = None
        regions = (872176049906130994, 872176162934231070, 872176229665603604)
        for region in regions:
            role = umcoc.get_role(region)
            if role in member.roles:
                regionrole = role
                next
        timezonerole = None
        timezones = (
            872129870132563989, 872129785294368778, 872129677483986945, 872129539881435228, 872128345561763940,
            872106199947034704, 872105998893076490, 872105793418297384, 872105941326233661, 872128958316052541,
            872129321408548905, 872128958316052541, 872128667730468874, 872128686202175538, 872108695562100766,
            872108818677506149, 872146132707471390, 872146185320792094, 872146367982739516, 872108362299478076, 
            872108431232876596, 872108476954968074, 872108590981320704, 872126515582734388, 872128205279068230, 
            872128503380869120)
        
        for timezone in timezones:
            role = umcoc.get_role(timezone)
            if role in member.roles:
                timezonerole = role
        return regionrole, timezonerole
        
    @profilegroup.group(name="update", aliases=("set",))
    async def profile_update(self, ctx: Context):
        """Update MCOC Profile"""

    @profile_update.command(name="ingame")
    async def profile_ingame(self, ctx: Context, ingame: str):
        await self.config.user(ctx.author).profile.ingame.set(ingame)
        await self.follow_up(ctx)
            
    @profile_update.command(name="started")
    async def profile_started(self, ctx: Context, date):
        """Date you started MCOC in mm/dd/yyyy

        Args:
            ctx (Context): [description]
            date (date): MM/DD/YYYY
        """
        if isinstance(date_parse(date), datetime.datetime):
            await self.config.user(ctx.author).profile.started.set(date)
            await self.follow_up(ctx)
            
    @profile_update.command(name="rosterss", aliases=("ss",))
    async def profile_roster_ss(self, ctx: Context):
        if len(ctx.message.attachments) > 0:
            for attachment in ctx.message.attachments:
                answer = await CDT.confirm(self, ctx, question="Do you want to save this attachment?", image=attachment)
                if answer: 
                    async with self.config.user(ctx.author).profile.roster_ss() as ss:
                        ss.append(attachment.url)
        await self.follow_up(ctx)
        

    @profile_update.command(name="mastery")
    async def profile_mastery_group(self, ctx: Context, mastery):
        """Set mastery screenshots

        Args:
            ctx (Context): [description]
            mastery (string): ['offense', 'defense', 'utility']
        """
        if mastery in ("offense", "defense", "utility", "collage"):
            async with self.config.user(ctx.author).profile() as profile:
                ss = profile[mastery]
                if len(ctx.message.attachments) > 0:
                    image = ctx.message.attachments[0]
                    answer = await CDT.confirm(self, ctx, question="Do you want to save this attachment?", image=image.url)
                    if answer: 
                        profile.update({mastery : image.url})
                        await self.follow_up(ctx)
                elif len(ctx.message.attachments) == 0:
                    answer = await CDT.confirm(self, ctx, question="Do you want to delete the existing offense screenshot?", image=ss)
                    if answer:
                        profile.update({mastery : None})
                        await self.follow_up(ctx)



    async def follow_up(self, ctx: Context):
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if can_react:
            await ctx.message.add_reaction("☑️")
        else:
            await ctx.send(random.choice(AFFIRMATIVE))

        


    @profilegroup.group(name="delete")
    async def profile_delete(self, ctx: Context): 
        """Delete MCOC Profile"""
    
    
    
    @profile_delete.command(name="profile")
    async def profile_delete_profile(self, ctx: Context):
        answer = await CDT.confirm(self, ctx, "Do you want to delete your MCOC profile?")
        if answer:
            async with self.config.user(ctx.author).profile() as profile:
                profile.clear()
            await self.follow_up(ctx)


    @profile_delete.command(name="rosterss")
    async def profile_delete_rosterss(self, ctx: Context):
        if len(await self.config.user(ctx.author).profile.roster_ss.all()) > 0:
            async with self.config.user(ctx.author).profile.roster_ss() as roster_ss:
                for ss in roster_ss:
                    answer = CDT.confirm("Do you want to delete this SS?", image=ss)
                    if answer:
                        roster_ss.pop(ss)
 