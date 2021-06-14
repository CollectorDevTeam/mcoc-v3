import discord
from redbot.core import Config, commands

from mcoc.cdtembed import Embed


class CdtTesting(commands.cog):
    """Test framework to debug new package files"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1000000000001)
        self.config.register_global()

    @commands.group(name="test", hidden=True)
    async def _test(self, ctx):
        """Test command group"""

    @test.command(name="say")
    async def _say(self, ctx, *, message):
        """Test send message"""
        await self.bot.send_message(ctx.message.channel, message)

    # @test.command(name="embed")
    # async def _embed(self, ctx, *, args):
    #     """Comma separated arguments
    #     title
    #     description
    #     color
    #     image
    #     thumbnail
    #     footer_text
    #     footer_url
    #     """
    #     default = {"title": None,
    #                "description": None,
    #                "color": None,
    #                "image": None,
    #                "thumbnail": None,
    #                "footer_text": None,
    #                "footer_url": None}

    #     eargs = args.split(",")

    #     parse_re = re.compile(r"""

    #         """, re.X)
    #     # default = {'tier': 0, 'difficulty': '', 'hp': 0, 'atk': 0, 'node': 0, 'nodes': '',
    #     #            'color': discord.Color.gold(), 'debug': 0, 'test': False}
    #     parse_re = re.compile(r"""\b(?:t(?:ier)?(?P<tier>[0-9]{1,2})
    #                 | hp?(?P<hp>[0-9]{2,6})
    #                 | a(?:tk)?(?P<atk>[0-9]{2,5})
    #                 | (?P<hpi>\d{2,6})\s(?:\s)*(?P<atki>\d{2,5})
    #                 # | (?P<nodes>(n\d+(n\d+(n\d+(n\d+(n\d+)?)?)?)?)?)?
    #                 | n(?:ode)?(?P<node>[0-9]{1,2}))
    #                 | (?:d(?P<debug>[0-9]{1,2}))\b
    #                 | (?P<star_filter>[1-6](?=(?:star|s)\b|(?:★|☆|\*)\B)) """, re.X)

    #     class_re = re.compile(
    #         r"""(?:(?P<class>sc(?:ience)?|sk(?:ill)?|mu(?:tant)?|my(?:stic)?|co(?:smic)?|te(?:ch)?))""", re.X)
