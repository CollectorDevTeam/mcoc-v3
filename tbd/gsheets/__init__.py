from .gsheets import GSheets


def setup(bot):
    cog = GSheets(bot)
    bot.add_cog(cog)