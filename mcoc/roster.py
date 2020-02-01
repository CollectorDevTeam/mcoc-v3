from redbot.core import commands
from redbot.core import Config
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
import discord
import asyncio
import contextlib
from redbot.core.utils import menus
from .CDT import CDT

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
        await self.roster_display(ctx, user)
        # await ctx.send("Roster command identified: {}".format(user.display_name))
        return

    async def roster_display(self, ctx, user):
        roster = self.config.user(user.id)
        print(roster.roster_enabled())
        if roster.roster_enabled():
            ctx.send("Prestige: {}".format(roster.prestige()))
        else:
            await create_roster(ctx)


    async def create_roster(self, ctx):
        embed = CDT.cdt_embed(ctx)
        embed.title = "Roster is not enabled:sparkles:"
        embed.description = "Would you like to enable your CollectorVerseRoster?"
        message = await ctx.send(embed=embed)
        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        if not can_react:
            message += " (y/n)"
        query: discord.Message = await ctx.send(message)
        if can_react:
            start_adding_reactions(query, ReactionPredicate.YES_OR_NO_EMOJIS, ctx.bot.loop)
            pred = ReactionPredicate.yes_or_no(query, ctx.author)
            event = "reaction_add"
        else:
            pred = MessagePredicate.yes_or_no(ctx)
            event = "message"
        try:
            await ctx.bot.wait_for(event, check=pred, timeout=30)
            print("Create Roster Predicate: {}".format(pred))
        except asyncio.TimeoutError:
            await query.delete()
            return

        if not pred.result:
            if can_react:
                await query.delete()
            else:
                await ctx.send(_("OK then."))
            return
        else:
            if can_react:
                with contextlib.suppress(discord.Forbidden):
                    await query.clear_reactions()



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



