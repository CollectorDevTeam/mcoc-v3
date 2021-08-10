
import json
import logging
import random
from mcoc.cdtcore import DIAGNOSTICS
from mcoc.cdtcore import CDT

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
            "https://cdn.discordapp.com/attachments/391330316662341632/865819301326880768/dadjoke5.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/865819305693675541/dadjoke6.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/865819308731138109/dadjoke7.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/865822723858104390/dadjoke8.png",
            "https://cdn.discordapp.com/attachments/391330316662341632/865822729675603988/dadjoke9.png"
            
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
        data = await CDT.create_embed(ctx, title="CollectorVerse Dad Jokes:sparkles:", description=joke, image=image, footer_text="Dad Jokes | CollectorDevTeam")
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
