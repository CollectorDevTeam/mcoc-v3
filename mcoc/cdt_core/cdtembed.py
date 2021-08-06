# import logging

import asyncio
import contextlib
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
from ..abc import MixinMeta, Context
from .discord_assets import Branding

import aiohttp
import discord

from redbot.core.utils import menus

#BRANDING
PATREON = 'https://www.patreon.com/collectorbot'
JJW_TIPJAR = ''
COLLECTOR_SQUINT = "https://cdn.discordapp.com/attachments/391330316662341632/867885227603001374/collectorbota.gif"

class Embed(MixinMeta):
    """Creates a CDT flavored discord.Embed and returns it to you"""

    @staticmethod
    async def create_embed(
        ctx: Context,
        color: discord.Colour = discord.Color.gold(),
        title: str = "",
        description: str = "",
        image: str = None,
        thumbnail: str = COLLECTOR_SQUINT,
        url: str = PATREON,
        footer_text: str = "Collector | Contest of Champions | CollectorDevTeam",
        footer_url: str = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png",
    ) -> discord.Embed:
        """Return a color styled embed with CDT footer, and optional title or description.
        user_id = user id string. If none provided, takes message author.
        color = manual override, otherwise takes gold for private channels, or author color for guild.
        title = String, sets title.
        description = String, sets description.
        image = String url.  Validator checks for valid url.
        thumbnail = String url. Validator checks for valid url."""
        if (
            isinstance(ctx.channel, discord.abc.GuildChannel)
            and str(ctx.author.colour) != "#000000"
        ):
            color = ctx.author.color
        # url = url or Branding.PATREON
        data = discord.Embed(color=color, title=title, url=url)
        if description and len(description) < 2048:
            data.description = description
        data.set_author(name=ctx.author.display_name,
                        icon_url=ctx.author.avatar_url)
        
        if image is not None:
            data.set_image(url=image)
        if thumbnail is not None:
            data.set_thumbnail(url=thumbnail)
        # if thumbnail != Branding.COLLECTOR_SQUINT:
        #     async with self.session.get(thumbnail) as re:
        #         if re.status != 200:
        #             thumbnail = Branding.COLLECTOR_SQUINT
        #             #might need additional validation on that url
        # data.set_thumbnail(thumbnail)
        data.set_footer(text=footer_text, icon_url=footer_url)
        return data

    async def confirm(self, ctx, question): #might need to remove self
        """Pass user a question, returns True or False"""
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if not can_react:
            question += " (y/n)"
        data = await Embed.create_embed(
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

    def get_controls(int = 0):
        controls = {
            # "<:arrowleft:735628703610044488>": menus.prev_page,
            # "<:circlex:735628703530483814>": menus.close_menu,
            # "<:arrowright:735628703840600094>": menus.next_page,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
        }
        big_controls = {
            "⏪": Embed.page_minus_five,
            "◀️": menus.prev_page,
            "❌": menus.close_menu,
            "▶️": menus.next_page,
            "⏩": Embed.page_plus_five,
        }
        if int is not None and int > 8:
            return big_controls
        return controls

    async def page_minus_five(
        ctx: Context,
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
            page = page + 5
        return await menus.menu(ctx, pages, controls, message=message, page=page, timeout=timeout)

    async def page_plus_five(
        ctx: Context,
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


