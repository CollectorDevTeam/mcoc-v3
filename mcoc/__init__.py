from mcoc.CDT import CDT
from mcoc.roster import ROSTER
# from .cdtdata import CDTDATA
# from .gshandler import GSHandler
# from .core import MCOC


# from mcoc.gshandler import GSHandler

def setup(bot):
    # bot.add_cog(MCOC())
    bot.add_cog(CDT())
    bot.add_cog(ROSTER())
    # bot.add_cog(CDTDATA())
    # bot.add_cog(GSHandler())