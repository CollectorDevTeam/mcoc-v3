from redbot.core import commands
from redbot.core import Config
from redbot.core.utils import embed
from redbot.core import checks ## Command check decorators

COLLECTOR_ICON = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png'

class ROSTER(commands.Cog):
    """Test User data creation cog"""
    def __init__(self):
        self.config = Config.get_conf(self, identifier=8675309)
        default_user = {
            "about": "",
            "gender": "",
            "ingame": "",
            "started": "",
            "roster": {},
            "roster_enabled": False,
            "masteries": {},
            "prestige": 0
        }
        default_champion = {
            "Awakened": 0,
            "Id": "",
            "Pi": 0,
            "Rank": 1,
            "Role": "",
            "Stars": 1,
            "Class": "",
            "Tags": [],
            "Date_Added_To_Roster": ""
        }
        default_guild = {
            "mcoc_enabled": False,
            "alliance_name": "",
            "alliance_tag": "",
            "alliance_about": "",
            "alliance_started": "",
            "alliance_invite": "",
            "alliance_poster_url": "",
            "alliance_officers_role": "",
            "alliance_bg1_role": "",
            "alliance_bg2_role": "",
            "alliance_bg3_role": "",
            "alliance_alliance_role":""
        }
        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

    @commands.command()
    async def mycom(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send("I can do stuff!")

    @commands.command()
    async def myembed(self, ctx):
        """This is a test embed field"""
        em = embed(title="Title", color=ctx.message.author.color, description="description text",
                   url="https://discordpy.readthedocs.io/en/v1.3.1/api.html#discord.Embed")
        em.set_author(name="CollectorDevTeam", url="https://patreon.com/collectordevteam", icon_url=COLLECTOR_ICON)

        em.set_footer(text="Requested by {}".format(ctx.message.author), icon_url=ctx.message.author.avatar)
        em.set_thumbnail(url="")
        em.set_image(url="")
        em.add_field(name="Field name",value="Field value",inline=True)

        await ctx.send(em)

