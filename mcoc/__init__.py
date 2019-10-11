from .cdtdata import CDTDATA

def setup(bot):
    bot.add_cog(CDTDATA(bot))
    # bot.add_cog(MCOC()) #load MCOC Cog
