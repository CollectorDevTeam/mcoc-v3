import discord
from redbot.core import Config, commands

from cdtcommon.cdtcommon import CdtCommon
from cdtcommon.cdtembed import Embed
from mcoc import snapshots

import json

from cdtcommon.cdtcommon import CdtCommon
from cdtcommon.cdtembed import Embed

__version__ = "32.0.0"

__config_structure = {
    "global" : {
        "champions": {},
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
            "root_path" : "snapshots/en/Standard",
            "bcg_en" : {
                "filepath": None,
                "strings": None,
            },
            "bcg_stat_en": {
                "filepath": None,
                "strings": None,
                },
            "character_bios" : {
                "filepath": [None],
                "strings": None,
                },
            "cutscenes_en": {
                "filepath": None,
                "strings": None,
                },
            "special_attacks": {
                "filepath": None,
                "strings": None,
                },
        }, # end global set
    "champion" : {
        "id" : None, #str unique champion id
        "bid" : None, #str unique auntm.ai champion file id
        "uid" : None, #str unique auntm.ai url id
        "json_keys": {
            "bio": []],
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
}

# class Champion - champion factory with all champion properties defined.

class Champions(commands.Cog):
    """A CollectorDevTeam package for Marvel"s Contest of Champions"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_global(**__config_structure["global"])
        # self.bot = bot

    @commands.group(aliases=("champ","champion","mcoc"), hidden=True)
    async def champions(self, ctx):
        data = Embed.create(title="Marvel Contest of Champions")
        data.description = "dummy group"
        
    @champions.group(aliases="import")
    async def champions_import(self, ctx):
        """Data import commands"""

    @champions_import.command(name="snapshots")
    async def champions_import_snapshots(self, ctx):
        snapshots = {}


    @champions.commands(name="info")
    async def champion_info(self, ctx):
        """Champion information"""

    @champions.command(name="test")
    async def _champ_test(self, ctx):
        await ctx.send("Champion test string")


    ## import functions
    async def loadjson(self, ctx, config_key: str):
        """need to read in JSON from file"""
        if config_key in await self.config.snapshots()
            filepath = "/snapshots/en/Standard/{}.json".format(config_key)
            with open('filename.txt', 'r') as f:
                array = json.load(f)

        # is dataIO the right way to read in files now?
        # file path stuff
        # probably want to put these in the config right?
