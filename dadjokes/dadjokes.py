
import json
import logging
import random
from cdtcommon.cdtdiagnostics import DIAGNOSTICS
from cdtcommon.cdtembed import Embed

import aiohttp
import discord
from redbot.core import checks, commands
from redbot.core.config import Config

log = logging.getLogger("red.CollectorDevTeam.dadjokes")
CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"


class DadJokes(commands.Cog):
    """Random dad jokes from icanhazdadjoke.com"""

    def __init__(self, bot):
        self.bot = bot
        self.diagnostics = DIAGNOSTICS(self.bot)
        self.dadjoke_images = [
            "https://cdn.discordapp.com/attachments/391330316662341632/725045045794832424/collector_dadjokes.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/725054700457689210/dadjokes2.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/725055822023098398/dadjokes3.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/725056025404637214/dadjokes4.png",
        ]
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command(
        aliases=(
            "joke",
            "dadjokes",
            "jokes",
        ),
    )
    async def dadjoke(self, ctx):
        """Gets a random dad joke."""
        author = ctx.message.author
        joke = await self.get_joke()
        image_url = random.choice(self.dadjoke_images)
        kwargs = {"content": f"{image_url}\n\n{joke}"}
        #if await ctx.embed_requested():
        data = await self.create(ctx, title="CollectorVerse Dad Jokes:sparkles:", description=joke, author=author)
 #           data.set_author

        await ctx.send(embed=data)

    async def get_joke(self):
        api = "https://icanhazdadjoke.com/slack"
        joke = None
        while joke is None:
            async with self.session.get(api) as response:
                result = await response.json()
                attachments = result["attachments"][0]
                joke = attachments["text"]
        return joke

    async def create(
        self,
        ctx: commands.Context,
        color: discord.Colour = discord.Color.gold(),
        title: str = "",
        description: str = discord.Embed.Empty,
        image: str = None,
        thumbnail: str = None,
        url: str = None,
        footer_text: str = None,
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

        if (
            isinstance(ctx.message.channel, discord.abc.GuildChannel)
            and str(ctx.author.colour) != "#000000"
        ):
            color = ctx.author.colour
        if url is None:
            url = PATREON
        data = discord.Embed(color=color, title=title, url=url)
        if description is not None:
            if len(description) < 1500:
                data.description = description
        data.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        if image:
            async with self.session.get(image) as re:
                if re.status == 200:
                    data.set_image(url=image)
                else:
                    log.info(f"Image URL Failure, code {re.status}")
                    log.info(f"Attempted URL:\n{image}")
        if thumbnail:
            async with self.session.get(thumbnail) as re:
                if re.status != 200:
                    log.info(f"Image URL Failure, code {re.status}")
                    log.info(f"Attempted URL:\n{thumbnail}")
                    thumbnail = CDT_LOGO
        else:
            thumbnail = CDT_LOGO
        data.set_thumbnail(url=thumbnail)
        data.set_image(url=random.choice(self.dadjoke_images))

        if not footer_text:
            footer_text = "Collector | Contest of Champions | CollectorDevTeam"
        if not footer_url is None:
            footer_url = CDT_LOGO
        data.set_footer(text=footer_text, icon_url=footer_url)
        return data


def setup(bot):
    n = DadJokes(bot)
    bot.add_cog(n)
