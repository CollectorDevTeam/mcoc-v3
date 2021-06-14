import discord


class DIAGNOSTICS:
    def __init__(self, bot):
        self.bot = bot

    async def log(self, ctx, channel, msg=None):
        """Logs message to daignostics channel"""
        # package = self._log(ctx, msg)
        await ctx.send(msg)
        return

    def _log(self, ctx, msg=None):
        """Builds log response"""
        message = "CollectorDevTeam diagnostics:\n```"
        if isinstance(ctx.message.channel, discord.abc.PrivateChannel):
            message += "Private Channel: [{}]\n".format(ctx.message.channel.id)
        elif isinstance(ctx.message.channel, discord.abc.GuildChannel):
            message += "guild:  [{0.message.guild.id}] {0.message.guild.name} \n".format(ctx)
            message += "Channel: [{0.message.channel.id}] {0.message.channel.name} \n".format(ctx)
        message += "User:    [{0.message.author.id}] {0.message.author.display_name} \n".format(
            ctx
        )
        if ctx.invoked_subcommand is not None:
            if ctx.message.content is None:
                message += "Subcommand Invoked: {0.invoked_subcommand}\n".format(ctx)
            else:
                message += "Subcommand Invoked: {0.invoked_subcommand}\n".format(ctx)
                message += "Conent: {0.message.content}\n".format(ctx)
        message.format(ctx)
        # elif ctx.invoked is not None:
        #     message += 'Invoked command: {0.invoked}'.format(ctx)
        if msg is not None:
            message += "Comment: {}\n".format(msg)
        message += "```"
        return message


def setup(bot):
    bot.add_cog(DIAGNOSTICS)
