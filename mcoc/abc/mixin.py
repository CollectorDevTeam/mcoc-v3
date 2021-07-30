from discord.ext.commands.core import guild_only
from redbot.core import commands
from redbot.core.commands import context
from cdtcommon.cdtcommon import CDT

@commands.group(name="mcoc", aliases=("champ","champions",))
@CDT.is_collectordevteam()
async def mcoccommands(self, ctx:commands.Context):
    """Marvel Contest of Champions commands"""
    pass 

@commands.group(name="alliance")
@CDT.is_supporter()
# @commands.guild_only()
@guild_only()
async def alliancecommands(self, ctx:commands.Context):
    """MCOC Alliance commands"""
    pass

@commands.group(name="roster")
@CDT.is_collectordevteam()
@CDT.is_supporter()
async def rostercommands(self, ctx:commands.context):
    """MCOC Roster commands"""
    pass

class MCOCMixin:
    """MCOC stuff"""
    c = mcoccommands
    a = alliancecommands
    r = rostercommands