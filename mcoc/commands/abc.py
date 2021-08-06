
from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdtcore import CDT


@commands.group(name="mcoc")
@CDT.is_collectordevteam()
async def mcocgroup(self, ctx: Context):
    """Marvel Contest of Champions commands"""
    pass 

@mcocgroup.group(name="set")
@CDT.is_collectordevteam()
async def mcocsettingsgroup(self, ctx: Context):
    """MCOC settings commands"""
    pass

