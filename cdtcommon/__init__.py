from redbot.core.bot import Red
from .cdtcommon import CDT


def setup(bot: Red):
    cog = CDT(bot)
    bot.add_cog(cog)
