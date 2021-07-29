import contextlib
from pickle import decode_long
import random
from typing import Optional
import asyncio

import discord
from discord.ext.commands.context import Context
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils import chat_formatting, menus
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from functools import wraps

from cdtcommon.cdtembed import Embed

import logging



log = logging.getLogger("red.CollectorDevTeam.cdtcommon")

_config_structure = {
    "commands": {
        "name" : None,
        "reporting_channel": None,  
    },
    "cdtcheck" :{
        "cdtguild" : 215271081517383682,
        "cdt" : 390253643330355200,
        "cst" : 390253719125622807,
        "guildowners" : 391667615497584650,
        "familyowners" : 731197047562043464,
        "tattletales" : 537330789332025364,
        "patrons": 408414956497666050,
        "credited_patrons": 428627905233420288,
        "cdt_boosters" : 736631216035594302
    }
}

class CdtCommon(commands.Cog):
    """
    CollectorDevTeam Common Files & Functions
    """
    CDTGUILD = 215271081517383682
    COLLECTORDEVTEAM = 390253643330355200
    COLLECTORSUPPORTTEAM = 390253719125622807
    GUILDOWNERS = 391667615497584650
    FAMILYOWNERS = 731197047562043464
    PATRONS: 408414956497666050
    CREDITED_PATRONS: 428627905233420288
    CDTBOOSTERS = 736631216035594302
    TATTLETALES = 537330789332025364

    def __init__(self, bot: Red):
        self.bot = bot
        # self.cdtguild = self.bot.get_guild(215271081517383682)
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )
        self.config.register_global(**_config_structure["cdtcheck"])


        # self.config.init_custom("checks", 1) # need to initialize first
        # self.config.register_custom("checks", **_config_structure["checks"])



    @commands.command(hidden=True, name="promote", aliases=("promo",))
    @commands.guild_only()
    async def cdt_promote(self, ctx, channel: discord.TextChannel, *, content):
        """Content will fill the embed description.
        title;content will split the message into Title and Content.
        An image attachment added to this command will replace the image embed."""
        authorized = self.check_collectorsupportteam(ctx)
        if authorized is not True:
            return
        else:
            pages = []
            # contents = content.split(";")
            # if len(contents) > 1:
            #     title = contents[0]
            #     description = contents[1]
            # else:
            #     title = "CollectorVerse Tips"
            #     description = content
            if len(ctx.message.attachments) > 0:
                image = ctx.message.attachments[0]
                # imgurl = image['url']
                imgurl = image.url
                # urllib.request.urlretrieve(imgurl, 'data/mcocTools/temp.png')
                # asyncio.wait(5)
                # newfile = await self.bot.file_upload(robotworkshop, 'data/mcocTools/temp.png')
                # image = newfile.attachments[0]
                # imgurl = image['url']
                # imagelist = []
                # for i in ctx.message.attachments.keys():
                #     imagelist.append(ctx.message.attachments[i]['url'])
            else:
                imagelist = [
                    "https://cdn.discordapp.com/attachments/391330316662341632/725045045794832424/collector_dadjokes.png",
                    "https://cdn.discordapp.com/attachments/391330316662341632/725054700457689210/dadjokes2.png",
                    "https://cdn.discordapp.com/attachments/391330316662341632/725055822023098398/dadjokes3.png",
                    "https://cdn.discordapp.com/attachments/391330316662341632/725056025404637214/dadjokes4.png",
                    "https://media.discordapp.net/attachments/391330316662341632/727598814327865364/D1F5DE64D72C52880F61DBD6B2142BC6C096520D.png",
                    "https://media.discordapp.net/attachments/391330316662341632/727598813820485693/8952A192395C772767ED1135A644B3E3511950BA.jpg",
                    "https://media.discordapp.net/attachments/391330316662341632/727598813447192616/D77D9C96DC5CBFE07860B6211A2E32448B3E3374.jpg",
                    "https://media.discordapp.net/attachments/391330316662341632/727598812746612806/9C15810315010F5940556E48A54C831529A35016.jpg",
                ]
                imgurl = random.choice(imagelist)
            thumbnail = "https://images-ext-1.discordapp.net/external/6Q7QyBwbwH2SCmwdt_YR_ywkHWugnXkMc3rlGLUnvCQ/https/raw.githubusercontent.com/CollectorDevTeam/assets/master/data/images/featured/collector.png?width=230&height=230"
            # for imgurl in imagelist:
            data = await Embed.create(
                ctx, title="CollectorVerse Tips:sparkles:", description=content, image=imgurl
            )
            data.set_author(
                name="{} of CollectorDevTeam".format(ctx.author.display_name),
                icon_url=ctx.author.avatar_url,
            )
            data.add_field(
                name="Alliance Template",
                value="[Make an Alliance Guild](https://discord.new/gtzuXHq2kCg4)\nRoles, Channels & Permissions pre-defined",
                inline=False,
            )
            data.add_field(
                name="Get Collector",
                value="[Invite](https://discord.com/oauth2/authorize?client_id=210480249870352385&scope=bot&permissions=8)",
                inline=False,
            )
            data.add_field(
                name="Support",
                value="[CollectorDevTeam Guild](https://discord.gg/BwhgZxk)",
                inline=False,
            )
            await channel.send(embed=data)
            # await self.bot.delete_message(ctx.message)
            # pages.append(data)
            # menu = PagesMenu(self.bot, timeout=30, add_pageof=True)
            # await menu.menu_start(pages=pages)

    @commands.command()
    @commands.guild_only()
    async def showtopic(self, ctx, channel: discord.TextChannel = None):
        """Show the Channel Topic in the chat channel as a CDT Embed."""
        channel = channel or ctx.channel
        topic = channel.topic
        if topic is not None and topic != "":
            data = await Embed.create(
                ctx, title="#{} Topic :sparkles:".format(channel.name), description=topic
            )
            data.set_thumbnail(url=ctx.message.guild.icon_url)
            await ctx.send(embed=data)
        else:
            await ctx.send("That channel does not have a topic")

    @commands.command(name="listmembers", aliases=("listusers", "roleroster", "rr"))
    async def _users_by_role(self, ctx, use_alias: Optional[bool] = True, *, role: discord.Role):
        """Embed a list of server users by Role"""
        guild = ctx.guild
        pages = []
        members = self._list_users(ctx, role, guild)
        if members:
            if use_alias:
                ret = "\n".join("{0.display_name}".format(m) for m in members)
            else:
                ret = "\n".join("{0.name} [{0.id}]".format(m) for m in members)
            for num, page in enumerate(chat_formatting.pagify(ret, page_length=200), 1):
                data = await Embed.create(
                    ctx,
                    title="{0.name} Role - {1} member{2}".format(role, len(members), "s" if not len(members) == 1 else ""),
                    description=page,
                    footer_text=f"Page {num} | CDT Embed"
                )
                pages.append(data)
            msg = await ctx.send(embed=pages[0])
            if len(pages) > 1:
                menus.start_adding_reactions(msg, self.get_controls())
                await menus.menu(ctx=ctx, pages=pages, controls=self.get_controls(), message=msg)
        else:
            await ctx.send(f"I could not find any members with the role {role.name}.")

    def _list_users(self, ctx, role: discord.Role, guild: discord.guild):
        """Given guild and role, return member list"""
        members = [m for m in guild.members if role in m.roles]
        return members or None

    def get_controls():
        controls = {
            # "<:arrowleft:735628703610044488>": menus.prev_page,
            # "<:circlex:735628703530483814>": menus.close_menu,
            # "<:arrowright:735628703840600094>": menus.next_page,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
        }
        return controls

    @commands.command(hidden=True)
    @commands.has_role(COLLECTORDEVTEAM)
    async def checktest(self, ctx, checking):
        if checking in ("cdt", "collectordevteam"):
            if await self.check_cdt(ctx):
                await ctx.send("If this message printed, then checktest passed cdt")










    async def tattle(ctx, channel, message):
        """"Someone's been a naughty boy/girl/it/zey/zim"""
        data = Embed.create(title="CDT Tattletales", description=message)
        data.add_field(name="Who", value="{ctx.author.name} [{ctx.author.id}]")
        data.add_field(name="What", value="{ctx.message.content}")
        data.add_field(name="Where", value="{ctx.guild.name} [{ctx.guild.id}]")
        data.add_field(name="When", value="{ctx.timestamp}")
        await ctx.bot.send(embed=data, channel=channel)



    async def get_user_confirmation(self, ctx, question):
        """Pass user a question, returns True or False"""
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if not can_react:
            question += " (y/n)"
        data = await Embed.create(
                    ctx,
                    title="Confirmation Request :sparkles:",
                    description=question,
                )
        
        pages = []
        pages.append(data)    
        query = await ctx.send(embed=pages[0])
        if can_react:
            menus.start_adding_reactions(query, ReactionPredicate.YES_OR_NO_EMOJIS)
            pred = ReactionPredicate.yes_or_no(query, ctx.author)
            event = "reaction_add"
        else: 
            pred = MessagePredicate.yes_or_no(ctx)
            event = "message"
        try:
             await ctx.bot.wait_for(event, check=pred, timeout=30)
        except asyncio.TimeoutError:
            await query.delete()
            return

        if not pred.result:
            if can_react:
                await query.delete()
            else:
                await ctx.send("Ok then. :sparkles:")
            return
        else:
            if can_react:
                with contextlib.suppress(discord.Forbidden):
                    await query.clear_reactions()

        return pred.result

    async def tattle(self, ctx, tale : str, tattle: discord.channel = 537330789332025364):
        await ctx.send(tale, channel=tattle)

    # @commands.group(name="cdtmonitor", alias="monitor")
    # @check_collectordevteam()




    @staticmethod
    def from_flat(flat, ch_rating):
        denom = 5 * ch_rating + 1500 + flat
        return round(100 * flat / denom, 2)

    @staticmethod
    def to_flat(per, ch_rating):
        num = (5 * ch_rating + 1500) * per
        return round(num / (100 - per), 2)


    def menupagify(self, ctx: Context, intext: str, title=None):
        """chat format string to pages, and set in embed object descriptions"""
        textpages = list(chat_formatting.pagify(text=intext, page_length=1800))
        menupages = []
        for page in textpages:
            p = Embed.create(ctx, description=page)
            if title is not None:
                p.title(title)
            menupages.append(p)
        return menupages

    async def cdtcheck(ctx, role_id):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(CdtCommon.CDTGUILD)
        checkrole = cdtguild.get_role(role_id)
        member = cdtguild.get_member(ctx.author.id)
        if member is None:
            CdtCommon.tattle(ctx, channel=cdtguild.get_channel(CdtCommon.TATTLETALES), message="User is not authorized")
            return False
        elif checkrole in member.roles:
            return True
        else:
            return True

class CdtCheck(commands):
    def is_collectordevteam():
        async def pred(ctx: commands.Context):
            checkrole = CdtCommon.COLLECTORDEVTEAM
            await CdtCommon.cdtcheck(ctx, checkrole)
            return commands.check(pred)
    
    def is_collectorsupportteam():
        async def pred(ctx: commands.Context):
            checkrole = CdtCommon.COLLECTORSUPPORTTEAM
            await CdtCommon.cdtcheck(ctx, checkrole)
            return commands.check(pred)


    def is_guildowners():
        async def pred(ctx: commands.Context):
            checkrole = CdtCommon.GUILDOWNERS
            await CdtCommon.cdtcheck(ctx, checkrole)
            return commands.check(pred)

    def is_familyowners():
        async def pred(ctx: commands.Context):
            checkrole = CdtCommon.FAMILYOWNERS
            await CdtCommon.cdtcheck(ctx, checkrole)
            return commands.check(pred)

    def is_supporter():
        async def pred(ctx: commands.Context):
            booster = await CdtCommon.cdtcheck(ctx, CdtCommon.CDTBOOSTERS)
            patron = await CdtCommon.cdtcheck(ctx, CdtCommon.PATRONS)
            credited_patron = await CdtCommon.cdtcheck(ctx, CdtCommon.CREDITED_PATRONS)
            if booster or patron or credited_patron:
                return True
            return commands.check(pred)

