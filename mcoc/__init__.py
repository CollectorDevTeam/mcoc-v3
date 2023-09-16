from mcoc.testing import CdtTesting

# from mcoc.mcoc import MCOC


async def setup(bot):
    # bot.add_cog(MCOC())
    await bot.add_cog(CdtTesting())
