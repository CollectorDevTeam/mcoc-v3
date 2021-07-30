from redbot.core import commands

from cdtcommon.abc.mixin import cdtcommands
from cdtcommon.abc.cdt import CDT
from cdtcommon.abc.abc import MixinMeta


class CDTDiagnostics(MixinMeta):
    """Collector Dev Team diagnostic commands"""
   
    @cdtcommands.group(name="check", aliases=("ctest",), invoke_without_command=True)
    async def checktest(self, ctx: commands.Context):
        """Check priviledge groups from CollectorDevTeam guild"""
        pass

    @checktest.command()
    @CDT.is_collectordevteam()
    async def cdt(self,ctx):
        """Check CollectorDevTeam"""
        await ctx.send("Dev Team test")


    @checktest.command()
    @CDT.is_collectorsupportteam()
    async def cst(self,ctx):
        """Check CollectorSupportTeam"""
        await ctx.send("Support Team test")


    @checktest.command(aliases=("go",))
    @CDT.is_guildowners()
    async def guildowner(self,ctx):
        """Check registered GuildOwners"""
        await ctx.send("GuildOwner test")


    @checktest.command(aliases=("fo",))
    @CDT.is_familyowners()
    async def familyowners(self,ctx):
        """Check registered FamilyOwners"""
        await ctx.send("supporter test")


    @checktest.command(aliases=("supporter", "patron", "booster"))
    @CDT.is_supporter()
    async def supporters(self,ctx):
        """Check registered Supporters: Boosters & Patrons"""
        await ctx.send("supporter test")
