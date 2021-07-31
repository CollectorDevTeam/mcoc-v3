import aiohttp
from .abc.exceptions import MODOKError
from .abc.mixin import CDTMixin, cdtcommands
from abc import ABC

# from pickle import decode_long
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from .abc.cdt import CDT

## Calculator type commands
from .commands.calculator import CDTCalculator
## Diagnostic commands
from .commands.cdtdiagnostics import CDTDiagnostics
from .commands.common import CDTCommon
from .commands.propaganda import CDTPromote

class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


_config_structure = {
    "commands": {
        "name" : None,
        "reporting_channel": None,  
    },
}
# CDTCalculator, CDTDiagnostics, 
class CDT_Cog(
    CDTCalculator, 
    CDTDiagnostics, 
    CDTPromote,
    CDTCommon,
    CDTMixin, 
    CDT,
    MODOKError,
    commands.Cog, 
    metaclass=CompositeMetaClass
    ):
    """
    CollectorDevTeam Common Files & Functions
    """
    
    __version__="0.0.1"
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )
        self.session = aiohttp.ClientSession
   
    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())