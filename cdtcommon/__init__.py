from .cdtcommon import CdtCommon
from .fetch_data import FetchCdtData


def setup(bot):
    bot.add_cog(CdtCommon(bot))
    bot.add_cog(FetchCdtData(bot))
