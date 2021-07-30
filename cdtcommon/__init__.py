from redbot.core.bot import Red
from .cdtcommon import CDTCog


def setup(bot: Red):
    bot.add_cog(CDTCog(bot))
