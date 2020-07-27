import discord
from redbot.core import commands, checks
from redbot.core.config import Config
from .cdtembed import Embed

class CdtCommon(commands.Cog):
    """
    Common Files
    """

    def __init__(self, bot):
        self.bot = bot
        self.Embed = Embed(self)
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )

    @commands.command(pass_context=True, no_pm=True)
    async def showtopic(self, ctx, channel: discord.TextChannel = None):
        """Play the Channel Topic in the chat channel."""
        if channel is None:
            channel = ctx.message.channel
        topic = channel.topic
        if topic is not None and topic != '':
            data = self.Embed.create(ctx, title='#{} Topic :sparkles:'.format(
                                     channel.name),
                                 description=topic)
            data.set_thumbnail(url=ctx.message.guil.icon_url)
            # data.set_footer(text='CollectorDevTeam', icon_url=COLLECTOR_ICON)
            await ctx.send(embed=data)
