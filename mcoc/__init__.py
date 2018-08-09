from .alliancewar  import AllianceWar
from .common.pages_menu import PagesMenu

def setup(bot):
    bot.add_cog(AllianceWar())
    bot.add_cog(mcoc())
