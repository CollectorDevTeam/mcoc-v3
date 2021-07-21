import random
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.config import Config
from redbot.core.utils import chat_formatting, menus

from .cdtembed import Embed

import logging

log = logging.getLogger("red.CollectorDevTeam.cdtcommon")

_config_structure = {
    "commands": {
        "name" : {},
        "reporting_channel": {},  
        "tattletales" : 537330789332025364,
    },
    "cdt_roles": {
        "cdt" : 390253643330355200,
        "cst" : 390253719125622807,
        "guildowners" : 391667615497584650,
        "familyowners" : 731197047562043464,
    }
}
class CdtCommon(commands.Cog):
    """
    Common Files
    """


    def __init__(self, bot):
        self.bot = bot
        self.cdtguild = self.bot.get_guild(215271081517383682)
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )
        self.config.register_global(**_config_structure["commands"])
        self.config.register_global(**_config_structure["cdt_roles"])

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
                menus.start_adding_reactions(msg, self._get_controls())
                await menus.menu(ctx=ctx, pages=pages, controls=self._get_controls(), message=msg)
        else:
            await ctx.send(f"I could not find any members with the role {role.name}.")

    def _list_users(self, ctx, role: discord.Role, guild: discord.guild):
        """Given guild and role, return member list"""
        members = [m for m in guild.members if role in m.roles]
        return members or None

    def _get_controls(self):
        controls = {
            # "<:arrowleft:735628703610044488>": menus.prev_page,
            # "<:circlex:735628703530483814>": menus.close_menu,
            # "<:arrowright:735628703840600094>": menus.next_page,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
        }
        return controls

    async def collectordevteam(self, ctx):
        """Verifies if calling user has either the trusted CollectorDevTeam role, or CollectorSupportTeam"""
        role_ids = (
            "390253643330355200",
            "390253719125622807",
        )
        for r in role_ids:
            self.roles.update({r: self._get_role(self.bot.get_server("215271081517383682"), r)})
            if self.roles[r] in ctx.author.roles:
                return True
                continue
        return False

    async def check_collectordevteam(self, ctx, user=None):
        """Checks if User is in CollectorDevTeam"""
        role = await discord.utils.get(self.cdtguild.roles, id=self.config.cdt_roles.cdt())
        if user is None:
            user = ctx.author
        checkuser = await discord.utils.get(self.cdtguild.members, id=user.id)
        if role in checkuser.roles:
            return True
        else:
            await ctx.send("CDT Authentication attempt failed, {0.name}{0.id} on {1.name}{1.id}".format(user, ctx.guild), 
            channel=await self.config.commands.tattletales())
            return False

    async def check_collectorsupportteam(self, ctx, user=None):
        """Checks if User is in CollectorSupportTeam"""
        role = await discord.utils.get(self.cdtguild.roles, id=self.config.cdt_roles.cst())
        print("CST role found")
        if user is None:
            user = ctx.author
            print("Message.author is user")
        checkuser = discord.utils.get(self.cdtguild.members, id=user.id)
        if checkuser is None:
            # print("User not found on CDT Guild")
            return False
        else:
            # print("User found on CDT guild")
            if role in checkuser.roles:
                return True # print("CollectorSupporTeam Authenticated")
            else :
                await ctx.send("CST Authentication attempt failed, {0.name}{0.id} on {1.name}{1.id}".format(user, ctx.guild), 
            channel=await self.config.commands.tattletales())
                return await self.check_collectordevteam(ctx, user)

    async def check_guildowners(self, ctx, user=None):
        """Checks if User is Registered GuildOwner in CollectorDevTeam"""
        role = await discord.utils.get(self.cdtguild.roles, id=self.config.cdt_roles.guildowners())
        if user is None:
            user = ctx.author
        checkuser = await discord.utils.get(self.cdtguild.members, id=user.id)
        if role in checkuser.roles:
            return True
        else:
            await ctx.send("CDT Authentication attempt failed, {0.name}{0.id} on {1.name}{1.id}".format(user, ctx.guild), 
            channel=await self.config.commands.tattletales())
            return False

    async def check_familyowners(self, ctx, user=None):
        """Checks if User is Registered GuildOwner in CollectorDevTeam"""
        role = await discord.utils.get(self.cdtguild.roles, id=self.config.cdt_roles.familyowners())
        if user is None:
            user = ctx.author
        checkuser = await discord.utils.get(self.cdtguild.members, id=user.id)
        if role in checkuser.roles:
            return True
        else:
            await ctx.send("CDT Authentication attempt failed, {0.name}{0.id} on {1.name}{1.id}".format(user, ctx.guild), 
            channel=await self.config.commands.tattletales())
            return False

    async def _get_user_confirmation(self, ctx, question):
        pages = []
        data = await Embed.create(
                    ctx,
                    title="Confirmation Request",
                    description=question,
                )
        pages.append(data)
        
        q = await ctx.send(embed=pages(0))
        confirm_controls = {'❎': False, '✅': True}

        menus.start_adding_reactions(q, confirm_controls)
        await menus.menu(ctx=ctx, pages=pages, controls=confirm_controls, message=q)

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
