from redbot.core import commands
from redbot.core import Config
from mcoc.cdt_library import CDT#, HashParser

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
        embed.title = "Test Embed 1"
        embed.description = "Description\nTest embed, ctx not passed."
        embed.add_field(name="Field name", value="Field value", inline=True)
        embed.set_image(url="https://cdn.discordapp.com/attachments/398210253923024902/672232058818658354/MCoC_CharacterPose-TheCollector-Current_4.png")
        embed.set_thumbnail(url="https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/images/featured/collector.png")
        await ctx.send(embed=embed)

    @commands.command()
    async def myembed2(self, ctx):
        """This is a test embed passing context."""

        embed = CDT.cdt_embed(self, ctx=ctx)
        embed.title = "Test Embed 2"
        embed.description = "Description field\nTest embed, ctx passed."
        await ctx.send(embed=embed)

    @commands.group()
    async def roster(self, ctx, *, hargs=''):
        # testphrase = self.HashParser.parse_with_user(ctx, hargs, **kwargs)
        user, hargs = self.get_mention(ctx, hargs)
        await ctx.send("Roster command identified: {}".format(user.display_name))
        return

    def get_mention(self, ctx, hargs):
        """Very basic user extractor"""
        mentions = ctx.message.mentions
        print(mentions)
        print(len(mentions))
        if len(mentions) == 0:
            return ctx.message.author, hargs
        if len(mentions) > 1:
            ctx.send("Only one user per Roster command")
            return None
        else:
            hargs = hargs.replace("{} ".format(mentions[0]), "")
            return mentions[0], hargs



