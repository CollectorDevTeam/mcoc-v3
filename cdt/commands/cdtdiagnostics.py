from redbot.core import commands
from redbot.core.bot import Red 
from redbot.core.config import Config

from ..abc.mixin import cdtcommands
from ..abc.cdt import CDT
from ..abc.abc import MixinMeta

DIAGNOSTICS = 871079325825376327
DIAGMSG = "who: {0.author.name} {0.author.id}\nwhere: {0.guild.name} {0.guild.id}\ncontent:```{0.message.content}```"

class CDTDiagnostics(MixinMeta):
    """Collector Dev Team diagnostic commands"""

    async def diaglog(self, ctx):
        await self.bot.get_channel(DIAGNOSTICS).send(DIAGMSG.format(ctx))

    @cdtcommands.group(name="check", invoke_without_command=True)
    async def checkgroup(ctx: commands.Context):
        """Check priviledge groups from CollectorDevTeam guild"""


    @CDT.is_collectordevteam()
    @checkgroup.command(name="cdt")
    async def checkgroupcdt(self, ctx):
        """Check CollectorDevTeam"""
        await ctx.send("Dev Team test")


    @CDT.is_collectorsupportteam()
    @checkgroup.command(name="cst")
    async def checkgroupcst(self, ctx):
        """Check CollectorSupportTeam"""
        await ctx.send("Support Team test")

    @CDT.is_guildowners()
    @checkgroup.command(name="guildowner", aliases=("go",))
    async def checkgroupguildowner(self, ctx):
        """Check registered GuildOwners"""
        await ctx.send("GuildOwner test")

    @CDT.is_familyowners()
    @checkgroup.command(name="familyowners", aliases=("fo",))
    async def checkgroupfamilyowners(self, ctx):
        """Check registered FamilyOwners"""
        await ctx.send("Family test")

    @checkgroup.command(name="supporters", aliases=("supporter", ))
    @CDT.is_supporter()
    async def checkgroupsupporters(self, ctx):
        """Check registered Supporters: Boosters & Patrons"""
        await ctx.send("Supporter test")

    @checkgroup.command(name="patron", aliases=("patrons",))
    @CDT.is_patron()
    async def checkgrouppatrons(self, ctx):
        """Check registered Patrons or Credited Patrons"""
        await ctx.send("Patron test")

    @checkgroup.command(name="booster", aliases=("boosters",))
    @CDT.is_booster()
    async def checkgroupboosters(self, ctx):
        """Check registered Server Boosters"""
        await ctx.send("Booster test")

    @checkgroup.command(name="all", aliases=("any",))
    @CDT.is_any_priviledged()
    async def checkgroupany(self, ctx):
        await ctx.send("Check all priviledged.")