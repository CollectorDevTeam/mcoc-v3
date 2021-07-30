import discord
from redbot.core.utils import menus
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
import asyncio
import contextlib

from redbot.core import commands
from redbot.core.commands import Context
from cdtcommon.abc.abc import MixinMeta
from cdtcommon.abc.cdtembed import Embed
from cdtcommon.abc.cdtcheck import CdtCheck
from cdtcommon.abc.fetch_data import FetchData
# from cdtcommon.abc.common import CommonFunctions

       
# class CDT(CommonFunctions, Embed, FetchData, CdtCheck, MixinMeta):
#     """will this work?"""

class CDT(Embed, FetchData, CdtCheck, MixinMeta):
    """common functions that are not {prefix} commands"""

    @staticmethod
    def from_flat(flat, ch_rating):
        denom = 5 * ch_rating + 1500 + flat
        return round(100 * flat / denom, 2)

    @staticmethod
    def to_flat(per, ch_rating):
        num = (5 * ch_rating + 1500) * per
        return round(num / (100 - per), 2)

    # def menupagify(self, ctx: Context, intext: str, title=None):
    #     """chat format string to pages, and set in embed object descriptions"""
    #     textpages = list(chat_formatting.pagify(text=intext, page_length=1800))
    #     menupages = []
    #     for page in textpages:
    #         p = CDT.create_embed(ctx, description=page)
    #         if title is not None:
    #             p.title(title)
    #         menupages.append(p)
    #     return menupages

    def list_role_members(self, ctx, role: discord.Role, guild: discord.guild):
        """Given guild & role, return list of members with role"""
        members = [m for m in guild.members if role in m.roles]
        return members or None

    async def confirm(self, ctx, question): #might need to remove self
        """Pass user a question, returns True or False"""
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if not can_react:
            question += " (y/n)"
        data = await CDT.create_embed(
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

    def get_controls(int = None):
        controls = {
            # "<:arrowleft:735628703610044488>": menus.prev_page,
            # "<:circlex:735628703530483814>": menus.close_menu,
            # "<:arrowright:735628703840600094>": menus.next_page,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
        }
        big_controls = {
            "⏪": CDT.page_minus_five,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
            "⏩": CDT.page_plus_five,
        }
        if int is not None and int > 8:
            return big_controls
        return controls

    async def page_minus_five(
        ctx: commands.Context,
        pages: list,
        controls: dict,
        message: discord.Message,
        page: int,
        timeout: float,
        emoji: str,
    ):
        """Extending Red menu controls to page +5 at a time for large pages menus"""
        perms = message.channel.permissions_for(ctx.me)
        if perms.manage_messages:  # Can manage messages, so remove react
            with contextlib.suppress(discord.NotFound):
                await message.remove_reaction(emoji, ctx.author)
        if page == len(pages) - 1:
            page = 0  # Loop around to the first item
        else:
            page = page - 5
        return await menus.menu(ctx, pages, controls, message=message, page=page, timeout=timeout)

    async def page_plus_five(
        ctx: commands.Context,
        pages: list,
        controls: dict,
        message: discord.Message,
        page: int,
        timeout: float,
        emoji: str,
    ):
        perms = message.channel.permissions_for(ctx.me)
        if perms.manage_messages:  # Can manage messages, so remove react
            with contextlib.suppress(discord.NotFound):
                await message.remove_reaction(emoji, ctx.author)
        if page == len(pages) - 1:
            page = 0  # Loop around to the first item
        else:
            page = page + 5
        return await menus.menu(ctx, pages, controls, message=message, page=page, timeout=timeout)

 