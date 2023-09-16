from .dadjokes import DadJokes

async def setup(bot):
    cog = DadJokes(bot)
    await bot.add_cog(cog)