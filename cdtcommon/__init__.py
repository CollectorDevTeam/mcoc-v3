from .cdtcommon import CdtCommon
from .fetch_data import FetchCdtData
from .calculator import Calculator


def setup(bot):
    bot.add_cog(CdtCommon(bot))
    bot.add_cog(FetchCdtData(bot))
    bot.add_cog(Calculator(bot))
