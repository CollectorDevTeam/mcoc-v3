from mcoc.CDT import CDT
from mcoc.cdtdata import CDTDATA
from mcoc.roster import ROSTER
from .mcoc import MCOC


# from mcoc.gshandler import GSHandler

def setup(bot):
    bot.add_cog(CDT())
    bot.add_cog(CDTDATA())
    bot.add_cog(MCOC())
    bot.add_cog(ROSTER())
    # bot.add_cog(GSHandler())