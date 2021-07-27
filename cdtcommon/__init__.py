# from .calculator import Calculator
from .cdtcommon import CdtCommon
# from .fetch_data import FetchData


def setup(bot):
    bot.add_cog(CdtCommon(bot))
    # bot.add_cog(FetchData(bot))
    # bot.add_cog(Calculator(bot))
