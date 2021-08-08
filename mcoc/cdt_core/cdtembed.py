# import logging

import asyncio
import contextlib
from typing import Optional
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

    async def confirm(self, ctx, question, image = None): #might need to remove self
        """Pass user a question, returns True or False"""
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if not can_react:
            question += " (y/n)"
        data = await Embed.create_embed(
                    ctx,
                    title="Confirmation Request :sparkles:",
                    description=question,
                )
        if image is not None:
            data.set_image(url=image)

        query = await ctx.send(embed=data)
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
            data.description="You couldn't even answer one simple question..."
            await ctx.send(embed=data)
            return

        if pred is not None:
            await query.delete()
            return pred.result

        elif not pred.result:
            if can_react:
                await query.delete()
                data.description = "You couldn't even answer one simple question..."
                await ctx.send(embed=data)
            else:
                await ctx.send("No reaction detected.  Nothing changes, peon. :sparkles:")
            return
        # else:
        #     if can_react:
        #         with contextlib.suppress(discord.Forbidden):
        #             await query.clear_reactions()


