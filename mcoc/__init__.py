from mcoc.data.cdtdata import CDTDATA
from .mcoc import MCOC
from mcoc.roster.roster import ROSTER
from mcoc.Lib.gshandler.gshandler import GSHandler

def setup(bot):
    bot.add_cog(CDTDATA())
    bot.add_cog(MCOC())
    bot.add_cog(ROSTER())
    bot.add_cog(GSHandler())