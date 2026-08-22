from redbot.core import commands

class AllianceCommands:
    def __init__(self, core):
        self.core = core

    @commands.group()
    async def alliance(self, ctx):
        """Alliance commands."""
        pass
