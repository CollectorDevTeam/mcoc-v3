import discord
from ..abc import rostergroup, MixinMeta, CompositeMetaClass
from ..cdtcore import CDT

import json


class RosterData(MixinMeta, metaclass=CompositeMetaClass):
    """Roster management class for MCOC"""

    @rostergroup.command(name="create")
    async def roster_create():
        roster = "abc"

    @rostergroup.command(name="read")
    async def roster_read(self, ctx, user : discord.User=None):
        if user is None:
            user = ctx.message.author
        roster = self.config.user(user.id).all()

    @rostergroup.command(name="upate", aliases=("add"))
    async def roster_update(self, ctx, champion_list:list):
        """Add champion to roster"""
        if ctx.author not in self.config():
            answer = await CDT.confirm(ctx, "No MCOC roster detected.\nWould you like to create a roster?")
            if answer:
                await self.config.register_user(**self.default_user)
            else:
                return
        # async with self.config.user(ctx.author).roster.champions() as champions:
            # for c in champion_list:
            #    validate c as champion
            #    if valid:  create champion object, add to roster
            # 

    @rostergroup.command(name="delete", aliases=("remove", "rm"))
    async def roster_delete(self, ctx, champion_list:list):
        # champions = parse_champion_list(champion_list)  #need a champion parser
        # delete_champions = "\n".join(champion.name for champion in champions)
        delete_champions = "bogus champion"
        answer = CDT.confirm(ctx, "Do you want to delete the following champions?\n{}".format(delete_champions))
        if answer:
            await self.config.user(ctx.author.id).clear()

    @rostergroup.command(name="purge")
    async def roster_purge(self, ctx):
        answer = CDT.confirm(ctx, "Are you sure you want to purge your MCOC roster?\nThis action cannot be reversed.")
        if answer:
            await self.config.user(ctx.author).clear()
            data = CDT.create_embed(ctx, title="Roster Purge complete", description="so dumb")
            await ctx.send(embed=data)

    @rostergroup.command(name="download")
    async def roster_download(self, ctx):
        """Roster download as [tbd]"""

    @rostergroup.command(name="import", aliases=("auntmai", "auntm.ai",))
    async def roster_auntmai_import():
        """Import roster from Auntm.ai"""

    ## ROSTER SETTINGS COMMAND GROUP
    @rostergroup.group(name="settings", aliases=("set"))
    async def rostersettingsgroup(self, ctx):
        """MCOC Roster settings"""
        # if nothing, show user settings

    @rostersettingsgroup.command(name="show")
    async def rostersettings_read(self, ctx):
        """Show current roster settings"""
        settings = await self.config.user(ctx.author).settings.all()
        await ctx.send(json.dumps(settings))

    @rostersettingsgroup.group(name="set")
    async def rosterupdategroup(self, ctx):
        """Set roster settings"""

    @rosterupdategroup(name="auntmai", hidden=True)
    async def set_auntmai_key(self, ctx, auntmai:str=None):
        """Set Auntmai intregration key"""
        currentkey = await self.config.user(ctx.author).settings.autnmai()
        if auntmai is not None:
            answer = CDT.confirm("Do you want to set ``{}`` as your auntmai account id?")
            if answer:
                await self.config.user(ctx.author).settings.auntmai.set(auntmai)
        elif auntmai is None and currentkey is not None:
            answer = CDT.confirm("Do you want to clear your Auntm.ai key? \nThis action is permanent.")
            if answer:
                await self.config.user(ctx.author).settings.auntmai.set(None)

        