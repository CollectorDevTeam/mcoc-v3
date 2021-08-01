#
# framework for storing maps urls and playing them into chat

from mcoc.abc import CompositeMetaClass, MixinMeta


class MapData(MixinMeta, metaclass=CompositeMetaClass):
    """MCOC Maps commands"""

    async def map_create(self, ctx):
        """Register MCOC Map"""

    async def map_read(self, ctx):
        """Read MCOC Map"""

    async def map_update(self, ctx):
        """Update MCOC Map"""

    async def map_delete(self, ctx): 
        """Delete MCOC Map"""