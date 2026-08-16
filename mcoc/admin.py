from redbot.core import commands

class AdminCommands:
    def __init__(self, core):
        self.core = core

    @commands.group()
    async def mcocadmin(self, ctx):
        """Admin commands."""
        pass

    @mcocadmin.command()
    async def syncinterval(self, ctx, hours: int):
        await self.core.config.sync_interval.set(hours)
        await ctx.send(f"Sync interval set to {hours} hours.")
