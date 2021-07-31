from redbot.core import commands
from redbot.core.bot import Red 
from redbot.core.config import Config

from cdtcommon.abc.mixin import cdtcommands
from cdtcommon.abc.cdt import CDT
from cdtcommon.abc.abc import MixinMeta

DIAGNOSTICS = 871079325825376327
DIAGMSG = "who: {0.author.name} {0.author.id}\nwhere: {0.guild.name} {0.guild.id}\ncontent:```{0.message.content}```"

class CDTDiagnostics(MixinMeta):
    """Collector Dev Team diagnostic commands"""
    # def __init__(self, *_args):
    #     self.config: Config
    #     self.bot: Red

    async def diaglog(self, ctx):
        await self.bot.get_channel(DIAGNOSTICS).send(DIAGMSG.format(ctx))

    @cdtcommands.group(name="check")
    async def checkgroup(self, ctx: commands.Context):
        """Check priviledge groups from CollectorDevTeam guild"""
        # await self.diaglog(ctx)
    
    @checkgroup.command(name="cdt")
    @CDT.is_collectordevteam()
    async def checkgroupcdt(self, ctx):
        """Check CollectorDevTeam"""
        await ctx.send("Dev Team test")


    @checkgroup.command(name="cst")
    @CDT.is_collectorsupportteam()
    async def checkgroupcst(self,ctx):
        """Check CollectorSupportTeam"""
        await ctx.send("Support Team test")


    @checkgroup.command(name="guildowner", aliases=("go",))
    @CDT.is_guildowners()
    async def checkgroupguildowner(self,ctx):
        """Check registered GuildOwners"""
        await ctx.send("GuildOwner test")


    @checkgroup.command(name="familyowners", aliases=("fo",))
    @CDT.is_familyowners()
    async def checkgroupfamilyowners(self,ctx):
        """Check registered FamilyOwners"""
        await ctx.send("Family test")


    @checkgroup.command(name="supporters", aliases=("supporter", "patron", "booster"))
    @CDT.is_supporter()
    async def checkgroupsupporters(self,ctx):
        """Check registered Supporters: Boosters & Patrons"""
        await ctx.send("supporter test")
