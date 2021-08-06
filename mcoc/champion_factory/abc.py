from abc import ABC, abstractmethod

from redbot.core import Config, commands
from redbot.core.bot import Red

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

