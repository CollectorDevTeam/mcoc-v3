import discord
import aiohttp

from redbot.core.commands import Context

import logging

log = logging.getLogger("red.CollectorDevTeam.cdtembed")


class Embed:
    """Creates a CDT Embed and returns it to you"""

    @staticmethod
    async def create(
        ctx: Context,
        color: discord.Colour = discord.Color.gold(),
        title: str = "",
        description: str = "",
        image: str = None,
        thumbnail: str = None,
        url: str = None,
        footer_text:str = None,
        footer_url: str = None,
        author_text: str = None,
    ) -> discord.Embed:
        """Return a color styled embed with CDT footer, and optional title or description.
        user_id = user id string. If none provided, takes message author.
        color = manual override, otherwise takes gold for private channels, or author color for guild.
        title = String, sets title.
        description = String, sets description.
        image = String url.  Validator checks for valid url.
        thumbnail = String url. Validator checks for valid url."""
        COLLECTOR_ICON = (
            "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
        )
        PATREON = "https://patreon.com/collectorbot"
        CDT_LOGO = (
            "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
        )
        client = aiohttp.ClientSession()

        if (
            isinstance(ctx.channel, discord.abc.GuildChannel)
            and str(ctx.author.colour) != "#000000"
        ):
            color = ctx.author.color
        url = url or PATREON
        data = discord.Embed(color=color, title=title, url=url)
        if description and len(description) < 2048:
            data.description = description
        data.set_author(
            name=ctx.author.display_name, icon_url=ctx.author.avatar_url
        )
        if image:
            async with client.get(image) as re:
                if re.status != 200:
                    log.info(f"Image URL Failure, code {re.status}")
                    log.info(f"Attempted URL:\n{image}")
                else:
                    data.set_image(url=image)
        thumbnail = thumbnail or CDT_LOGO
        if thumbnail and thumbnail != CDT_LOGO:
            async with client.get(thumbnail) as re:
                if re.status != 200:
                    log.info(f"Thumbnail URL Failure, code {re.status}")
                    log.info(f"Attempted URL:\n{thumbnail}")
                    thumbnail = CDT_LOGO
        data.set_thumbnail(url=thumbnail)
        if not footer_text:
            footer_text = "Collector | Contest of Champions | CollectorDevTeam"
        if not footer_url:
            footer_url = CDT_LOGO
        data.set_footer(text=footer_text, icon_url=footer_url)
        await client.close()
        return data
