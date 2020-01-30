from redbot.core import commands
import pygsheets
# from redbot.core import Config
# from .common.pages_menu import PagesMenu as Menu
#
# GOOGLECREDENTIALS = ''
#
diagnostics = '672501245180772353'
class GSHandler(commands.Cog):
    def __init__(self):
        pass
    # self.config = Config.get_conf(self, identifier=gshandler2019)


    @commands.command()
    async def testapi(self, ctx):
        """Test Command String"""
        collectordevteam = await ctx.bot.get_shared_api_tokens("collectordevteam")
        Client = await self.authorize(ctx, collectordevteam)
        if Client is not None:
            await ctx.send("Client authenticated")

    async def authorize(self, ctx, token):
        await ctx.send("Token: {}".format(token))
        try:
            return pygsheets.authorize(custom_credentials=token)
        except FileNotFoundError:
            err_msg = 'API token failed to authenticate'
            await ctx.send(content=err_msg, channel=ctx.bot.get_channel(diagnostics))
            raise FileNotFoundError(err_msg)
