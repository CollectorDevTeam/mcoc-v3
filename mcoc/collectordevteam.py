from redbot.core import commands
import discord


class CDT(commands.Cog):

    COLLECTOR_ICON = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png'
    # def _init__(self):
    #     pass

    def cdt_embed(self, ctx=None):
        """Discord Embed constructor with CollectorDevTeam defaults."""
        emauthor_icon_url = CDT.COLLECTOR_ICON
        if ctx is not None:
            emcolor = ctx.message.author.color
            emauthor = "Requested by {0.display_name} | {0.id}".format(ctx.message.author)
            emauthor_icon_url = ctx.message.author.avatar_url
        else:
            emcolor = discord.Color.gold()
            emauthor = "CollectorDevTeam"

        embed = discord.Embed(title="Test Embed | Title Field", color=emcolor,
                              description="CollectorDevTeam | description text")
        embed.set_author(name=emauthor, icon_url=emauthor_icon_url)

        embed.set_footer(text="[CollectorDevTeam](https://patreon.com/collectordevteam)", icon_url=CDT.COLLECTOR_ICON)
        return embed