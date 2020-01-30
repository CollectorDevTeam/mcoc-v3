from redbot.core import commands
from redbot.core import Config
import discord
from .collectordevteam import CDT

from redbot.core import checks ## Command check decorators



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

        embed = CDT.cdt_embed(self)
        embed.add_field(name="Field name", value="Field value", inline=True)

        await ctx.send(embed=embed)

    @commands.command()
    async def myembed2(self, ctx):
        """This is a test embed removing thumbnail and images."""

        embed = CDT.cdt_embed(self, ctx=ctx)
        embed.set_footer(text="Requested by {0.display_name} | {0.id}".format(ctx.message.author),
                         icon_url=ctx.message.author.avatar_url)
        await ctx.send(embed=embed)

