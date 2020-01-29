# from .cdtdata import CDTDATA
# from .test import Mycog
from .mcoc import MCOC
from .roster import ROSTER

def setup(bot):
    # bot.add_cog(CDTDATA(bot))
    # bot.add_cog(MCOC()) #load MCOC Cog
    bot.add_cog(MCOC())
    bot.add_cog(ROSTER())