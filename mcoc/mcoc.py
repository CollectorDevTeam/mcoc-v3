import aiohttp
import discord
from .commands import Commands
from .cdtcore import CDT
from .abc import CompositeMetaClass
from redbot.core.bot import Red
from redbot.core.config import Config
import logging

# log = logging.getLogger('red.CollectorDevTeam.mcoc')

default_champion =  {
    "id" : None, #str unique champion id
    "bid" : None, #str unique auntm.ai champion file id
    "uid" : None, #str unique auntm.ai url id
    "json_bio": [], #list of json keys 
    "json_description" : [], #list of json keys 
    "json_sp1": [], #list of json keys 
    "json_sp2" : [], #list of json keys 
    "json_sp3" : [], #list of json keys 
    "json_abilities": [], #list of json keys 
    "aliases" : [], #all known aliases, check against known for clashes
    "name": None, #formal name
    "class": None, 
    "release_date": None, #date
    "prerelease_date": None, 
    "tags": [], #list of tags
    "weaknesses": [], #list of weaknesses
    "strengths" : [], #list of strengths
    "t1_release" : None, #release_date + x
    "t2_release" : None, #release_date + x
    "t3_release" : None, #release_date + x
    "t4_release" : None, #release_date + x
    "t5_release" : None, #release_date + x
    "t6_release" : None #release_date + x
}

default_user = {
    "profile": {
        "roster" : [], # List of champion dict
        "roster_screenshots": [],
        "alliance_ids": [],
        "ingame": None,
        "paths": {
            "aq5":[],
            "aq6":[],
            "aq7":[],
            "aw": [],
        },
        "settings": {
            "auntmai": None, #str auntmai key,
            "hide_t1" : False,
            "hide_t2" : False,
            "hide_t3" : False,
            "hide_t4" : False,
            "hide_t5" : False,
            "hide_t6" : False,    
            "mastery_offense_screenshot":None,
            "mastery_defense_screenshot": None,
            "mastery_utility-screenshot": None,
            "mastery_collage_screenshot": None,
            "ingame": None,
            "started": None
        },
    },
},

alliance_registry = {
    "family" : {},
    "alliances" : {},
},

default_mcoc = {
    "xref_champions": {
    },
    "synergies" : None, #dictionary of {synergy_key: {}} 
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
} # end global set,

default_roster_champion = {
    "bid": None,
    "rank": 1,
    "sigLvl": 0
}

class MCOCCog(Commands, CDT, metaclass=CompositeMetaClass):
    """Marvel Contest of Champions"""

    __version__="3.0.0a"

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_user(**default_user)
        # self.config.register_global(**default_global)
        # self.config.init_custom("mcoc", 2017201819811978)
        self.config.register_global("mcoc", **default_mcoc)
        self.config.register_global("alliances_registry", **alliance_registry)
        self.session = aiohttp.ClientSession
        self.default_user_profile = default_user
    
    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())


    
