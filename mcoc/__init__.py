# from .cdtdata import CDTDATA
# from .test import Mycog
from .mcoc import MCOC
from .roster import ROSTER
from .gshandler import GSHandler

def setup(bot):
    # bot.add_cog(CDTDATA())
    # bot.add_cog(MCOC()) #load MCOC Cog
    bot.add_cog(MCOC())
    bot.add_cog(ROSTER())
    bot.add_cog(GSHandler(bot))