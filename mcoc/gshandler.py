from redbot.core import commands
from redbot.core import Checks
import pygsheets
# from redbot.core import Config
# from .common.pages_menu import PagesMenu as Menu
#
# GOOGLECREDENTIALS = ''
#
class GSHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, identifier=gshandler2019)


    @commands.command()
    async def testapi(self, ctx):
        """Test Command String"""
        collectordevteam = await self.bot.get_shared_api_tokens("collectordevteam")
        await ("Token: "+collectordevteam)
        try:
            return pygsheets.authorize(custom_credentials=collectordevteam)
        except FileNotFoundError:
            err_msg = 'API token failed to authenticate'
            await ctx.send(err_msg)
            raise FileNotFoundError(err_msg)
