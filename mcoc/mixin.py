from redbot.core import commands


@commands.group(name="champions", aliases=("mcoc"))
async def mcoccommands(self,ctx:commands.Context):
    """Marvel Contest of Champions commands"""
    pass 

class MCOCMixin:
    """MCOC stuff"""
    c = mcoccommands
