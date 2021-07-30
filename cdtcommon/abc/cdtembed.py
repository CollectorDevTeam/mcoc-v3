# import logging

from cdtcommon.abc.abc import MixinMeta

# import aiohttp
import discord
from redbot.core.commands import Context

#BRANDING
CDTLOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
COLLECTOR_SQUINT = "https://cdn.discordapp.com/attachments/391330316662341632/867885227603001374/collectorbota.gif"
COLLECTOR_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"

# session = aiohttp.ClientSession()

class Embed(MixinMeta):
    """Creates a CDT Embed and returns it to you"""

    @staticmethod
    async def create_embed(
        ctx: Context,
        color: discord.Colour = discord.Color.gold(),
        title: str = "",
        description: str = "",
        image: str = None,
        thumbnail: str = None,
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
        # COLLECTOR_ICON = (
        #     "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
        # )
        # PATREON = "https://patreon.com/collectorbot"
        # CDT_LOGO = (
        #     "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
        # )


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
        if image:
            async with MixinMeta.session.get(image) as re:
                if re.status != 200:
                    # log.info(f"Image URL Failure, code {re.status}")
                    # log.info(f"Attempted URL:\n{image}")
                # else:
                    data.set_image(url=image)
        thumbnail = thumbnail or COLLECTOR_SQUINT
        if thumbnail and thumbnail != COLLECTOR_SQUINT:
            async with MixinMeta.session.get(thumbnail) as re:
                if re.status != 200:
                    # log.info(f"Thumbnail URL Failure, code {re.status}")
                    # log.info(f"Attempted URL:\n{thumbnail}")
                    thumbnail = COLLECTOR_SQUINT
        data.set_thumbnail(url=thumbnail)
        data.set_footer(text=footer_text, icon_url=footer_url)
        # await session.close()
        return data