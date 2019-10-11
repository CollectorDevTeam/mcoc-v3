from redbot.core import commands
from redbot.core import Config
from .common.pages_menu import PagesMenu as Menu

class MCOC():
    """A CollectorDevTeam package for Marvel's Contest of Champions"""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True, aliases=['champs',])
    async def champ(self, ctx):
        """Champion information"""

    @champ.command(name='test')
    async def _champ_test(self, ctx):
        await ctx.send('Champion test string')
