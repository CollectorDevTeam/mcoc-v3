from .core import CollectorBot

async def setup(bot):
    await bot.add_cog(CollectorBot(bot))
