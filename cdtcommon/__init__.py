from .cdtcommon import cdtcommon


def setup(bot):
    cog = cdtcommon(bot)
    bot.add_cog(cog)