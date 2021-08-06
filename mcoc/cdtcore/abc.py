from abc import ABC
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core import commands
from redbot.core.commands import Context

class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    def __init__(self, *_args):
        self.config: Config
        self.bot: Red