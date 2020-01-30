from .cdtdata import CDTDATA
from .mcoc import MCOC
from .roster import ROSTER
from .gshandler import GSHandler

def setup(bot):
    bot.add_cog(CDTDATA())
    bot.add_cog(MCOC())
    bot.add_cog(ROSTER())
    bot.add_cog(GSHandler())