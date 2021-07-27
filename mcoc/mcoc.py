import discord
import os 

from datetime import datetime

from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting, menus

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
            "relative_path" : "snapshots\\en\\Standard",
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

    @champions_data.command(name="check")
    async def json_key_check(self, ctx, json_key=None):
        async with self.config.snapshots.words() as words:
            keys = words.keys()
            if json_key is None:
                question = "json_key_check: There are currently {} json_keys registered.\nDo you want a listing?".format(len(keys))
                answer = await CdtCommon.get_user_confirmation(question)
                if answer:
                    listing = "\n".join(k for k in keys)
                    pages = chat_formatting.pagify(listing, page_length=1000)
                    await menus.menu(ctx, pages=pages)
            elif json_key is not None and json_key in keys:
                await ctx.send("keys found.  testing")
                await ctx.send("{}".format(words[json_key]["v"]))
            else:
                await ctx.send("{} not found in words".format(json_key))

    # @champions_data.commands(name="purge")
    # async def dataset_delete(self, ctx, dataset=None):
    #     """MCOC data purge"""
    #     if dataset in ("snapshot", "snapshots", "words"):
    #         answer = await CdtCommon.get_user_confirmation("Do you want to delete {} dataset?".format(dataset))
    #     if answer:
    #         if dataset is "snapshot" or dataset is "snapshots":
    #             await self.config.snapshots.clear()
    #         elif dataset is "words":
    #             await self.config.words.clear()
    
    
    @champions_data.group(name="import")
    async def champions_import(self, ctx):
        """Data import commands
        snapshot - scrape data from translation files"""

    @champions_import.command(name="snapshot")
    async def champions_import_snapshot(self, ctx):
        snapshots = {}
        async with self.config.snapshots.json_files() as json_files:
            await ctx.send("for key in {}:".format(json_files))
            for key in json_files.keys():
                readin = await self.loadjson(ctx, key)
                async with self.config.words() as words:
                    words.update(readin["strings"])
                json_files[key].update(readin)


    # @champions.commands(name="info")
    # async def champion_info(self, ctx):
    #     """Champion information"""

    # @champions.command(name="test")
    # async def _champ_test(self, ctx, ):



    ## import functions
    async def loadjson(self, ctx, config_key: str):
        """Read in JSON file, return dict"""
        snapshot_file = {"meta": {}, "strings": {}}
        await ctx.send("loadjson: reading {} json file".format(config_key))
        cwd = os.getcwd()
        relative_path = await self.config.snapshots.relative_path()
        filepath = "{}\\{}\\{}.json".format(cwd, relative_path, config_key)
        if os.path.isfile(filepath):
            await ctx.send("loadjson: os filepath is valid file")
            with open(filepath, 'r') as f:
                array = json.load(f)
                stringlist = array["strings"] #list of strings
                await ctx.send("loadjson: crawling {} json_strings".format(len(stringlist)))
                strings = {}
                for i in len(stringlist):
                    for k, v in stringlist[i]:
                        if "vn" in pkg.keys():
                            vn = pkg["vn"]
                            if isinstance(vn, int):
                                vn = str(vn)
                        else:
                            vn = "0.0.0"
                        pkg = {k : {"v" : v , "vn": vn}}
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

