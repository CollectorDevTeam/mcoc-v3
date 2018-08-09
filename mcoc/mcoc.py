import discord
from discord.ext import commands
import json
import requests
from .common.pages_menu import PagesMenu as Menu

class mcoc()

    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True, aliases=['champs',])
    async def champ(self, ctx):
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @champ.command(name='test')
    async def _champ_test(self, ctx):
        await ctx.send('Champion test string')
