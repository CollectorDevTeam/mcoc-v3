from abc.mixin import MCOCMixin, mcoccommands
import discord
from redbot.core.bot import Red
from redbot.core import commands
from abc import ABC
from mcoc.abc.champ_data import ChampData
from mcoc.abc.alliance_data import AllianceData
from mcoc.abc.roster_data import RosterData

class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""

class MCOCCog(ChampData, RosterData, AllianceData, MCOCMixin, metaclass=CompositeMetaClass):
    """Marvel Contest of Champions"""

    __version__="3.0.0a"
    def __init__(self, bot: Red):
        super().__init__(bot)

    
