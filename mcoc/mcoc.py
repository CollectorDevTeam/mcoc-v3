from redbot.core import Config
from redbot.core import commands
from .common.pages_menu import PagesMenu as Menu

class MCOC():
    """A CollectorDevTeam package for Marvel's Contest of Champions"""
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(

        )
        self.bot = bot

    @commands.group(pass_context=True, aliases=['champs',])
    async def champ(self, ctx):
        """Champion information"""

    @champ.command(name='test')
    async def _champ_test(self, ctx):
        await ctx.send('Champion test string')
