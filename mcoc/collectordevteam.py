from redbot.core import commands
import discord


class CDT(commands.Cog):
    COLLECTOR_ICON = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png'
    COLLECTOR_FEATURED = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/images/featured/collector.png'
    BASEPATH = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"
    PATREON = 'https://patreon.com/collectorbot'
    KABAM_ICON = 'https://imgur.com/UniRf5f.png'
    COLORS = {1: discord.Color(0x3c4d3b), 2: discord.Color(0xa05e44), 3: discord.Color(0xa0aeba),
                  4: discord.Color(0xe1b963), 5: discord.Color(0xf55738), 6: discord.Color(0x07c6ed),
                  'Cosmic': discord.Color(0x2799f7), 'Tech': discord.Color(0x0033ff),
                  'Mutant': discord.Color(0xffd400), 'Skill': discord.Color(0xdb1200),
                  'Science': discord.Color(0x0b8c13), 'Mystic': discord.Color(0x7f0da8),
                  'All': discord.Color(0x03f193), 'Superior': discord.Color(0x03f193),
                  'default': discord.Color.gold(), 'easy': discord.Color.green(),
                  'beginner': discord.Color.green(), 'medium': discord.Color.gold(),
                  'normal': discord.Color.gold(), 'heroic': discord.Color.red(),
                  'hard': discord.Color.red(), 'expert': discord.Color.purple(),
                  'master': discord.Color.purple(), 'epic': discord.Color(0x2799f7),
                  'uncollected': discord.Color(0x2799f7), 'symbiote': discord.Color.darker_grey(),
                  }

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

        embed = discord.Embed(color=emcolor)
        embed.set_footer(text=emauthor, icon_url=emauthor_icon_url)
        return embed

    @staticmethod
    async def fetch_json(url, session):
        async with session.get(url) as response:
            raw_data = json.loads(await response.text())
        return raw_data