
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
        image = random.choice(self.dadjoke_images)
        kwargs = {"content": f"{image}\n\n{joke}"}
        #if await ctx.embed_requested():
        data = await Embed.create(ctx, title="CollectorVerse Dad Jokes:sparkles:", description=joke, image=image, footer_text="Dad Jokes | CollectorDevTeam")
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

def setup(bot):
    n = DadJokes(bot)
    bot.add_cog(n)
