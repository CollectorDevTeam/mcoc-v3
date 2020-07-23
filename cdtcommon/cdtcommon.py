import discord
from redbot.core import commands, checks
from redbot.core.config import Config


class cdtcommon(commands.Cog):
    """
    Common Files
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )
