import discord

from datetime import datetime

from redbot.core import Config, commands
from redbot.core.bot import Red

from cdtcommon.cdtcommon import CdtCommon
from cdtcommon.cdtembed import Embed

# from mcoc.champion import ChampionFactory

import json

__version__ = "32.0.0"

_config_structure = {
    "global" : {
        "champions": {

        },
        "default_champion" : {
            "id" : None, #str unique champion id
            "bid" : None, #str unique auntm.ai champion file id
            "uid" : None, #str unique auntm.ai url id
            "json_keys": {
                "bio": [],
                "description" : [],
                "sp1": [],
                "sp2" : [],
                "sp3" : [],
                "abilities": [], 
                },
            "aliases" : [],
            "name": None,
            "class": None,
            "release_date": None,
            "prerelease_date": None,
            "tags": [],
            "weaknesses": [],
            "strengths" : [],
            "tier_availability" : {
                "t1" : None,
                "t2" : None,
                "t3" : None,
                "t4" : None,
                "t5" : None,
                "t6" : None
            },
        },
        "synergies" : None,
        "classes": {
            "Cosmic": discord.Color(0x2799f7), 
            "Tech": discord.Color(0x0033ff),
            "Mutant": discord.Color(0xffd400), 
            "Skill": discord.Color(0xdb1200),
            "Science": discord.Color(0x0b8c13), 
            "Mystic": discord.Color(0x7f0da8),
            "All": discord.Color(0x03f193), 
            "Superior": discord.Color(0x03f193), 
            "default": discord.Color.light_grey(),
        }, 
        "snapshots" : {
            "root_path" : "snapshots/en/Standard/",
            "bcg_en" : {
                "meta": None,
                "strings": None,
            },
            "bcg_stat_en": {
                "meta": None,
                "strings": None,
                },
            "character_bios" : {
                "meta": None,
                "strings": None,
                },
            "special_attacks": {
                "meta": None,
                "strings": None,
                },
        }, # end snapshots
        "words": {}, #all words
    }, # end global set
}

# class Champion - champion factory with all champion properties defined.

class Champions(commands.Cog):
    """A CollectorDevTeam package for Marvel"s Contest of Champions"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=21978198120172018)
        self.config.register_global(**_config_structure["global"])
        # self.bot = bot

    @commands.group(aliases=("champ","champion","mcoc"))
    async def champions(self, ctx):
        data = await Embed.create(ctx, title="Marvel Contest of Champions")
        data.description = "dummy group"
        

    @champions.group(aliases=("data",), hidden=True)
    async def champions_data(self, ctx):
        """Data commands"""
        if await CdtCommon.check_collectordevteam(self, ctx):
            pass
        else:
            await CdtCommon.tattle("Unauthorized attempt to manipulate ChampData")



    @champions_data.command(name="test")
    async def _champ_test(self, ctx, snapshot_key, json_key):
        if json_key in await self.config.snapshots(snapshot_key):
            await ctx.send("keys found.  testing")
            await ctx.send("{}".format(await self.config.snapshots(snapshot_key).json_key()))
        elif snapshot_key not in await self.config.snapshots():
            await ctx.send("``{}`` not found in snapshots".format(snapshot_key))
        elif json_key not in await self.config.snapshots(snapshot_key):
            await ctx.send("``{}`` not found in snapshot".format(json_key))

    @champions_data.group(aliases=("import",))
    async def champions_import(self, ctx):
        """Data import commands"""

    @champions_import.command(name="snapshot")
    async def champions_import_snapshot(self, ctx):
        snapshots = {}
        keys = await self.config.snapshots()
        for key in keys:
            await self.loadjson(ctx, key)


    # @champions.commands(name="info")
    # async def champion_info(self, ctx):
    #     """Champion information"""

    # @champions.command(name="test")
    # async def _champ_test(self, ctx, ):



    ## import functions
    async def loadjson(self, ctx, config_key: str):
        """need to read in JSON from file"""
        snapshot_file = {}
        if config_key in await self.config.snapshots():
            filepath = "{}{}.json".format(await self.config.snapshots().root_path(), config_key)
            with open(filepath, 'r') as f:
                array = json.load(f)
                stringlist = array["strings"] #list of strings
                snapshot_file.update({"meta" : array["meta"]})
                for i in array["meta"]["string_count"]:
                    pkg = stringlist[i]
                    for k, v in pkg:
                        if "vn" in pkg.keys():
                            snapshot_file.update({k : {"v" : v , "vn": pkg["vn"]}})
                        else:
                            snapshot_file.update({k : {"v": v, "vn" : 0 }})
        await self.config.snapshots(config_key).set(snapshot_file)
        await ctx.send("```{}```".format(await self.config.snapshots(config_key).meta()))

    


        # is dataIO the right way to read in files now?
        # file path stuff
        # probably want to put these in the config right?


    # @champions.group(aliases="make", hidden=True)
    # async def champions_make(self, ctx):
    #     """Manual create champion commands"""


    # @champions_make.command(name="new")
    # async def champions_make_new(self, ctx, uid):
    #     newchamp = await ChampionFactory.create_champion(uid)
    #     if newchamp is not None:
    #         await self.config.champions.register_custom(uid, newchamp)  
    #         return
    
    # @champions_make.command(name="set")
    # async def champions_make_set(self, ctx, uid, property, value):
    #     if uid not in await self.config.champions():
    #         await ctx.send("uid ``{}`` is not registered, please check again".format(uid))
    #         return
    #     else:
    #         if property not in await self.config.champions(uid):
    #             await ctx.send("Property ``{}`` is not a valid champion property".format(property))
    #             return

