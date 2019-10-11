from .common.pages_menu import PagesMenu
from .cdtdata import CDTDATA


def setup(bot):
    bot.add_cog(CDTDATA())
    # bot.add_cog(MCOC()) #load MCOC Cog
