from .core import MCOC

__all__ = ["MCOC"]

async def setup(bot):
    await bot.add_cog(MCOC(bot))
