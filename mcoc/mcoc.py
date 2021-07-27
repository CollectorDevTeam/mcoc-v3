import discord
import os 

from datetime import datetime

from redbot.core import Config, commands
from redbot.core.bot import Red

from cdtcommon.cdtcommon import CdtCommon
from cdtcommon.cdtembed import Embed

# from mcoc.champion import ChampionFactory

import json

__version__ = "32.0.0"

CDTGUILD = 215271081517383682
COLLECTORDEVTEAM = 390253643330355200
COLLECTORSUPPORTTEAM = 390253719125622807
GUILDOWNERS = 391667615497584650
FAMILYOWNERS = 731197047562043464

_config_structure = {
    "global" : {
        "champions": {

        },
        "default_champion" : {
            "id" : None, #str unique champion id
            "bid" : None, #str unique auntm.ai champion file id
            "uid" : None, #str unique auntm.ai url id
            "json_keys": {
                "bio": [], #list of json keys 
                "description" : [], #list of json keys 
                "sp1": [], #list of json keys 
                "sp2" : [], #list of json keys 
                "sp3" : [], #list of json keys 
                "abilities": [], #list of json keys 
                },
            "aliases" : [], #all known aliases, check against known for clashes
            "name": None, #formal name
            "class": None, 
            "release_date": None, #date
            "prerelease_date": None, 
            "tags": [], #list of tags
            "weaknesses": [], #list of weaknesses
            "strengths" : [], #list of strengths
            "tier_availability" : {
                "t1" : None, #release_date + x
                "t2" : None, #release_date + x
                "t3" : None, #release_date + x
                "t4" : None, #release_date + x
                "t5" : None, #release_date + x
                "t6" : None #release_date + x
            },
        },
        "synergies" : None, #dictionary of {synergy_key: {}} 
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
            "root_path" : "snapshots\\en\\Standard",
            "json_files": {
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
            },
        }, # end snapshots
        "words": {}, #all words
    }, # end global set
}

# class Champion - champion factory with all champion properties defined.

class Champions(commands.Cog):
    """A CollectorDevTeam package for Marvel"s Contest of Champions"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=21978198120172018)
        self.config.register_global(**_config_structure["global"])

    @commands.group(aliases=("champ","champion","mcoc"))
    async def champions(self, ctx):
        data = await Embed.create(ctx, title="Marvel Contest of Champions")
        data.description = "dummy group"
        

    @champions.group(aliases=("data",), hidden=True)
    @commands.has_role(COLLECTORDEVTEAM)
    async def champions_data(self, ctx):
        """Data commands"""
        

    # @champions_data.command(name="test")
    # async def _champ_test(self, ctx, snapshot_key, json_key):
    #     if json_key in await self.config.snapshots(snapshot_key):
    #         await ctx.send("keys found.  testing")
    #         await ctx.send("{}".format(await self.config.snapshots(snapshot_key).json_key()))
    #     elif snapshot_key not in await self.config.snapshots():
    #         await ctx.send("``{}`` not found in snapshots".format(snapshot_key))
    #     elif json_key not in await self.config.snapshots(snapshot_key):
    #         await ctx.send("``{}`` not found in snapshot".format(json_key))

    @champions_data.group(aliases=("import",))
    async def champions_import(self, ctx):
        """Data import commands"""

    @champions_import.command(name="snapshot")
    async def champions_import_snapshot(self, ctx):
        snapshots = {}
        async with self.config.snapshots.json_files() as keys:
            await ctx.send("for key in {}:".format(keys))
            for key in keys.keys():
                readin = await self.loadjson(ctx, key)
                async with self.config.words() as words:
                    words.update(readin["strings"])
                async with self.config.snapshots() as snapshots:
                    snapshots.key.update(readin)


    # @champions.commands(name="info")
    # async def champion_info(self, ctx):
    #     """Champion information"""

    # @champions.command(name="test")
    # async def _champ_test(self, ctx, ):



    ## import functions
    async def loadjson(self, ctx, config_key: str):
        """Read in JSON file, return dict"""
        snapshot_file = {"meta": {}, "strings": {}}
        await ctx.send("reading {} json file".format(config_key))
        if config_key in await self.config.snapshots():
            cwd = os.getcwd()
            await ctx.send("cwd: {}".format(cwd))
            
            filepath = "{}\\{}\\{}.json".format(cwd, relative_path, config_key)
            with open(filepath, 'r') as f:
                array = json.load(f)
                stringlist = array["strings"] #list of strings
                strings = {}
                for i in len(stringlist):
                    for k, v in stringlist[i]:
                        if "vn" in pkg.keys():
                            pkg = {k : {"v" : v , "vn": pkg["vn"]}}
                        else:
                            pkg = {k : {"v" : v }}
                        strings.update(pkg)
                        await ctx.send("```json\n{}```".format(pkg))
                snapshot_file.update({"meta" : array["meta"], "strings": strings})
        return snapshot_file

    


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

