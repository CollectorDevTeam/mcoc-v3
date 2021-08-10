from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdt_core import CDT

class MapData(MixinMeta, metaclass=CompositeMetaClass):
    """MCOC Maps commands"""

    @commands.group(name="maps")
    @CDT.is_collectordevteam()
    async def mapgroup(self, ctx: Context):
        """MCOC Maps commands"""
        pass

    @mapgroup.command(name="create")
    async def map_create(self, ctx: Context):
        """Register MCOC Map"""
        pass

    @mapgroup.command("read")
    async def map_read(self, ctx: Context):
        """Read MCOC Map"""
        pass

    @mapgroup.command("update")
    async def map_update(self, ctx: Context):
        """Update MCOC Map"""
        pass

    @mapgroup.command("delete")
    async def map_delete(self, ctx: Context): 
        """Delete MCOC Map"""
        pass