import discord
from redbot.core.bot import Red
from redbot.core.config import Config
from mcoc.abc.abc import MCOCMixinMeta
from mcoc.abc.mixin import rostercommands
from cdtcommon.cdtcommon import CDT

_config_structure = {
    "user": {
        "roster" : {
            "champions" : [] # List of champion dict
        },
        "auntmai": None, #str auntmai key,
        "settings": {
            "hide_t1" : False,
            "hide_t2" : False,
            "hide_t3" : False,
            "hide_t4" : False,
            "hide_t5" : False,
            "hide_t6" : False
         }
    },
    "dummy_roster":{
    },
    "champion" : {
        "bid": None,
        "rank": 1,
        "sigLvl": 0
    }
}

class RosterData(MCOCMixinMeta):
    """Roster management class for MCOC"""

    def __init__(self, *_args):
        super().__init__(*_args)
        self.config = Config.get_conf(self, identifier=31978198120172018)
        self.config.register_user(**_config_structure["user"])

    @rostercommands.command(name="create")
    async def roster_create():
        roster = "abc"

    @rostercommands.command(name="read")
    async def roster_read(self, ctx, user : discord.User=None):
        if user is None:
            user = ctx.message.author
        roster = self.config.user(user.id).all()

    @rostercommands.command(name="upate", aliases=("add"))
    async def roster_update(self, ctx, champion_list:list):
        """Add champion to roster"""
        if ctx.author not in self.config():
            answer = await CDT.confirm(ctx, "No MCOC roster detected.\nWould you like to create a roster?")
            if answer:
                await self.config.register_user(**_config_structure["user"])
            else:
                return
        async with self.config.user(ctx.author).roster.champions() as champions:
            # for c in champion_list:
            #    validate c as champion
            #    if valid:  create champion object, add to roster
            # 

    @rostercommands.command(name="delete", aliases=("remove", "rm"))
    async def roster_delete(self, ctx, champion_list:list):
        # champions = parse_champion_list(champion_list)  #need a champion parser
        # delete_champions = "\n".join(champion.name for champion in champions)
        delete_champions = "bogus champion"
        answer = CDT.confirm(ctx, "Do you want to delete the following champions?\n{}".format(delete_champions))

    @rostercommands.command(name="purge")
    async def roster_purge(self, ctx):
        answer = CDT.confirm(ctx, "Are you sure you want to purge your MCOC roster?\nThis action cannot be reversed.")
        if answer:
            await self.config.user(ctx.author).clear()
            data = CDT.create_embed(ctx, title="Roster Purge complete", description="so dumb")
            await ctx.send(embed=data)

    @rostercommands.command(name="download")
    async def roster_download(self, ctx):
        """Roster download as [tbd]"""

    @rostercommands.command(name="import", aliases=("auntmai", "auntm.ai",))
    async def roster_auntmai_import():
        """Import roster from Auntm.ai"""

    ## ROSTER SETTINGS COMMAND GROUPD
    @rostercommands.group(name="settings", aliases=("set"))
    async def rostersettings(self, ctx):
        """MCOC Roster settings"""
        # if nothing, show user settings

    @rostersettings.command(name="show")
    async def rostersettings_show(self, ctx):
        """Show current roster settings"""

    @rostersettings.command(name="set")
    async def rostersettings_set(self, ctx):
        """Set roster settings"""
        