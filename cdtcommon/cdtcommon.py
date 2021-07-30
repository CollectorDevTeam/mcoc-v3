from cdtcommon.abc.mixin import CDTMixin, cdtcommands
from abc import ABC

from pickle import decode_long
import random
from typing import Optional

import discord

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils import chat_formatting, menus


from cdtcommon.abc.cdt import CDT
from cdtcommon.calculator import CDTCalculator
from cdtcommon.cdtdiagnostics import CDTDiagnostics

class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


_config_structure = {
    "commands": {
        "name" : None,
        "reporting_channel": None,  
    },
}
# CDTCalculator, CDTDiagnostics, 
class CDTCog(CDTCalculator, CDTDiagnostics, CDTMixin, commands.Cog, metaclass=CompositeMetaClass):
    """
    CollectorDevTeam Common Files & Functions
    """
    
    __version__="0.0.1"
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )


    @cdtcommands.command(name="promote", aliases=("promo",))
    @CDT.is_collectorsupportteam()
    async def cdt_promote(self, ctx, channel: discord.TextChannel, *, content):
        """Content will fill the embed description.
        title;content will split the message into Title and Content.
        An image attachment added to this command will replace the image embed."""
        pages = []
        if len(ctx.message.attachments) > 0:
            image = ctx.message.attachments[0]
            imgurl = image.url
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
       
        data = await CDT.create_embed(
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

    @commands.command()
    @commands.guild_only()
    async def showtopic(self, ctx, channel: discord.TextChannel = None):
        """Show the Channel Topic in the chat channel as a CDT Embed."""
        channel = channel or ctx.channel
        topic = channel.topic
        if topic is not None and topic != "":
            data = await CDT.create_embed(
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
        members = CDT.list_role_members(ctx, role, guild)
        # members = guild.get_members()
        if members:
            if use_alias:
                ret = "\n".join("{0.display_name}".format(m) for m in members)
            else:
                ret = "\n".join("{0.name} [{0.id}]".format(m) for m in members)
            for num, page in enumerate(chat_formatting.pagify(ret, page_length=200), 1):
                data = await CDT.create_embed(
                    ctx,
                    title="{0.name} Role - {1} member{2}".format(role, len(members), "s" if not len(members) == 1 else ""),
                    description=page,
                    footer_text=f"Page {num} | CDT Embed"
                )
                pages.append(data)
            msg = await ctx.send(embed=pages[0])
            if len(pages) > 1:
                menus.start_adding_reactions(msg, self.get_controls())
                await menus.menu(ctx=ctx, pages=pages, controls=CDT.get_controls(), message=msg)
        else:
            await ctx.send(f"I could not find any members with the role {role.name}.")