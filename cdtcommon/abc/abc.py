from abc import ABC, abstractmethod
import aiohttp

from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.commands import Context

## blatantely learning from / stealing from / Toxic-Cogs ##

class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    #Single session used in all CDTClasses
    session = aiohttp.ClientSession

    def __init__(self, bot: Red):
        self.config: Config
        self.bot: Red