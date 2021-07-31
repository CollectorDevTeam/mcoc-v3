# import logging

from .abc import MixinMeta

import aiohttp
import discord
from redbot.core.commands import Context

#BRANDING
CDTLOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
COLLECTOR_SQUINT = "https://cdn.discordapp.com/attachments/391330316662341632/867885227603001374/collectorbota.gif"
COLLECTOR_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"

session = aiohttp.ClientSession()

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
        url: str = None,
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
        url = url or PATREON
        data = discord.Embed(color=color, title=title, url=url)
        if description and len(description) < 2048:
            data.description = description
        data.set_author(name=ctx.author.display_name,
                        icon_url=ctx.author.avatar_url)
        if image is not None:
            print(image)
            async with session.get(image) as re:
                if re.status == 200:
                    data.set_image(url=image)
        if thumbnail != COLLECTOR_SQUINT:
            async with session.get(thumbnail) as re:
                if re.status != 200:
                    thumbnail = COLLECTOR_SQUINT
                    #might need additional validation on that url
        data.set_thumbnail(url=thumbnail)
        data.set_footer(text=footer_text, icon_url=footer_url)
        return data