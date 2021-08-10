from .user_data import ProfileData
from .alliance_data import AllianceData
from .champ_data import ChampData
from .map_data import MapData
from .roster_data import RosterData
from .modoksays import MODOKSays
from ..abc import CompositeMetaClass
from redbot.core import commands
from redbot.core.commands import Context
from ..cdt_core import CDT


# @commands.group(name="mcoc")
# # @CDT.is_collectordevteam()
# async def mcocgroup(self, ctx: Context):
#     """Marvel Contest of Champions commands"""
#     pass 

# @mcocgroup.group(name="set")
# @CDT.is_collectordevteam()
# async def mcocsettingsgroup(self, ctx: Context):
#     """MCOC settings commands"""
#     pass



class CdtCommands(AllianceData, ChampData, MapData, RosterData, ProfileData, MODOKSays, commands.Cog, metaclass=CompositeMetaClass):

# class CdtCommands(MODOKSays, metaclass=CompositeMetaClass):

    '''Class joining all command subclasses'''

    @commands.command()
    async def test(self, ctx: Context):
        await ctx.send("test")
        await ctx.send("Literally, all i do is say test")
        await ctx.send("and say that I say it..")


