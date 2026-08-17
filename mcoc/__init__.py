from .core import MCOC

async def setup(bot):
    await bot.add_cog(MCOC(bot))
