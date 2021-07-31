
from cdt.abc.modokerror import MODOKError
from ..abc.mixin import CDTMixin
from ..abc.cdt import CDT

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting, menus
from typing import Optional

class CDTCommon(CDTMixin):

    @commands.command(name="modok", hidden=True)
    async def modok_says(self, ctx):
        await CDT.raw_modok_says(self, ctx)
        
    @commands.command(name="modokerror")
    async def modok_error(self, ctx):
        try:
            a = (1/0)
        except:
            raise MODOKError("!!error!! YOU CANNOT DIVIDE BY ZERO !!error!!")
    

    @commands.command()
    @commands.guild_only()
    async def showtopic(self, ctx, channel: Optional [discord.TextChannel]):
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
    async def users_by_role(self, ctx, use_alias: Optional[bool] = True, *, role: discord.Role):
    
        """Embed a list of server users by Role"""
        guild = ctx.guild
        pages = []
        members = CDT.list_role_members(self, ctx, role, guild)
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
                menus.start_adding_reactions(msg, CDT.get_controls(len(pages)))
                await menus.menu(ctx=ctx, pages=pages, controls=CDT.get_controls(len(pages)), message=msg)
        else:
            await ctx.send(f"I could not find any members with the role {role.name}.")
