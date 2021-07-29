from typing import Sequence
import discord
import os 

from datetime import datetime

from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting, menus

from cdtcommon.cdtcommon import CdtCommon, CdtCheck, Embed
# from cdtcommon.cdtembed import Embed
from cdtcommon.fetch_data import FetchData

import requests
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
        "urls": {
            "bcg_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/bcg_en.json",
            "bcg_stat_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/bcg_stat_en.json",
            "special_attacks_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/special_attacks_en.json",
            "masteries_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/masteries_en.json",
            "character_bios_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/character_bios_en.json",
            "cutscenes_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/cutscenes_en.json",
        },
        "snapshots" : {
            "bcg_en" : {
                "meta": {},
                "strings": {},
            },
            "bcg_stat_en": {
                "meta": {},
                "strings": {},
            },
            "character_bios" : {
                "meta": {},
                "strings": {},
            },
            "special_attacks": {
                "meta": {},
                "strings": {},
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
    # @commands.has_role(CdtCommon.COLLECTORDEVTEAM) 
    @CdtCheck.is_collectordevteam()
    async def champions_data(self, ctx):
        """Data commands""" 

    @champions_data.command(name="check", aliases=("words",))
    async def json_key_check(self, ctx, json_key=None):
        async with self.config.words() as words:
            keys = words.keys()
            if json_key is None and len(keys) == 0:
                await ctx.send("There are currently {} json keys registered.".format(len(keys)))
            if json_key is None and len(keys) > 0:
                question = "json_key_check: There are currently {} json_keys registered.\nDo you want a listing?".format(len(keys))
                answer = await CdtCommon.get_user_confirmation(self, ctx, question)
                if answer:
                    listing = "\n".join(k for k in keys)
                    pages = list(chat_formatting.pagify(listing, page_length=1000))
                    await menus.menu(ctx, pages=pages, controls=CdtCommon.get_controls())
            elif json_key is not None and json_key in keys:
                await ctx.send("keys found.  testing")
                await ctx.send("{}".format(words[json_key]['v'])) # should be a dict of {"v": <something>, "vn": }
                await ctx.send("Version {}".format(words[json_key]['vn']))
            else:
                await ctx.send("{} not found in words".format(json_key))
        return


    @champions_data.command(name="delete", aliases=("purge",))
    async def champions_data_delete(self, ctx, dataset):
        """MCOC data purge"""
        if dataset in ("snapshot", "snapshots", "words"):
            answer = await CdtCommon.get_user_confirmation(self, ctx, "Do you want to delete {} dataset?".format(dataset))
            if answer:
                answer2 = await CdtCommon.get_user_confirmation(self, ctx, "Are you sure?  This is a delete you moron.")
                if answer2:
                    if dataset is "snapshot" or dataset is "snapshots":
                        # async with self.config.snapshots() as snapshots:
                        #     snapshots.clear_all_globals()
                        await self.config.snapshots.clear_all_globals()
                        async with self.config.snapshots() as snapshots:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(snapshots.keys())))
                    elif dataset is "words":
                        # async with self.config.words() as words:
                        await self.config.words.clear_all_globals()
                        async with self.config.words() as words:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(words.keys())))
        return
    

    @champions_data.group(name="import")
    async def champions_import(self, ctx):
        """Data import commands
        snapshot - scrape data from translation files"""

    @champions_import.command(name="json")
    async def champions_import_json(self, ctx, json_file=None):
        # data = Embed.create(ctx, title="CDT Snapshot Import", description="status")
        # description = "status"
        # status = await ctx.send(embed=data) # need to find the current version of edit message
        async with self.config.urls() as urls:
            jkeys = urls.keys()
            if json_file in jkeys:
                jkeys = [json_file] 
            # await ctx.send("champion_import_json: processing {}".format(jkeys))            
            for j in jkeys:
                # description+="\nFetching {}".format(j)
                # data.description(description)
                # await status.edit(embed=data)
                # await ctx.send("champions_import_json, fetch url\n{}".format(urls[j]))
                filetext = await FetchData.aiohttp_http_to_text(ctx, urls[j])
                if filetext is None:
                    # description+="\nBad fetch of {}".format(j)
                    # data.description(description)
                    # await status.edit(embed=data)
                    # await ctx.send("aiohttp to json failure, returned None")
                    continue
                # answer = await CdtCommon.get_user_confirmation(self, ctx, "Would you like to review the http_to_json output?")
                # if answer:
                #     print(filetext)
                #     pages = chat_formatting.pagify(text=filetext, page_length=1800)
                #     pagelist =list(pages)
                #     try: 
                #         await menus.menu(ctx, pages=pages, controls=CdtCommon.get_controls())
                #     except:
                #         await menus.menu(ctx, pages=pagelist, controls=CdtCommon.get_controls())

                if filetext is not None:
                    # description+="\nGood fetch.  Parsing."
                    # data.description(description)
                    # await status.edit(embed=data)
                    jsonfile = await FetchData.convert_kabamfile_to_json(ctx, filetext)
                    if jsonfile is not None:
                        async with self.config.words() as words:
                            words.update(jsonfile["strings"])
                        async with self.config.snapshots() as snapshots:
                            snapshots.update({j : jsonfile})
                    else:
                        await ctx.send("textfile_to_json did not return json/dict")







    # @champions_import.command(name="snapshot")
    # async def champions_import_snapshot(self, ctx):
    #     snapshots = {}
    #     async with self.config.snapshots.json_files() as json_files:
    #         keys = json_files.keys()
        
    #     await ctx.send("for key in {}:".format(json_files))
    #     for key in keys:
    #         readin = await self.loadjson(ctx, key)
    #         async with self.config.words() as words:
    #             words.update(readin["strings"])
    #         async with self.config.snapshots.json_files(key) as json_file:
    #             json_file.update({"meta": readin["meta"], "strings" : readin["strings"]})


    # @champions.commands(name="info")
    # async def champion_info(self, ctx):
    #     """Champion information"""

    # @champions.command(name="test")
    # async def _champ_test(self, ctx, ):





    


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

