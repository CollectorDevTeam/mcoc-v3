from .calculator import Calculator
from .cdtcommon import CdtCommon
from .fetch_data import FetchCdtData


async def setup(bot):
    await bot.add_cog(CdtCommon(bot))
    # await bot.add_cog(FetchCdtData(bot))
    await bot.add_cog(Calculator(bot))
