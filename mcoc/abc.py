from abc import ABC, abstractmethod
import aiohttp

from .cdtcore import CDT
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import Context

## blatantely learning from / stealing from / Toxic-Cogs ##

class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    def __init__(self, *_args):
        self.config: Config
        self.bot: Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


@commands.group(name="mcoc", aliases=("champ","champions",))
@CDT.is_collectordevteam()
async def mcocgroup(self, ctx:commands.Context):
    """Marvel Contest of Champions commands"""
    pass 

@commands.group(name="alliance")
@CDT.is_supporter()
@commands.guild_only()
async def alliancegroup(self, ctx:commands.Context):
    """MCOC Alliance commands"""
    pass

@commands.group(name="roster")
@CDT.is_collectordevteam()
@CDT.is_supporter()
async def rostergroup(self, ctx:commands.context):
    """MCOC Roster commands"""
    pass

@commands.group(name="mcocset", aliases=("set",))
async def settingsgroup(self, ctx:commands.Context):
    """MCOC Cog settings commands"""
    pass