from redbot.core.bot import Red
from .cdtcommon import CDT


def setup(bot: Red):
    bot.add_cog(CDT(bot))
