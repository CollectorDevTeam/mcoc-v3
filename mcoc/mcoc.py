import aiohttp
from .commands import Commands
from .cdtcore import CDT
from .abc import CompositeMetaClass
from redbot.core.bot import Red
from redbot.core.config import Config

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
    "roster" : [], # List of champion dict
    "auntmai": None, #str auntmai key,
    "settings": {
        "hide_t1" : False,
        "hide_t2" : False,
        "hide_t3" : False,
        "hide_t4" : False,
        "hide_t5" : False,
        "hide_t6" : False
        },
        "profile":{},
},


default_global = {
    "alliances": {},
    "families": {},
    "champions": {
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
} # end global set,

default_roster_champion = {
    "bid": None,
    "rank": 1,
    "sigLvl": 0
}

default_alliance = {
    "guild": None,  # int guild id
    "name": "Default Name",  # str
    "tag": "ABCDE",  # str
    "leader" : None,
    "officers": None,  # int For the role id
    "members": None,  # int For the role id
    "bg1": None,
    "bg2": None,
    "bg3": None,
    "poster": None,  # str An image link, NOTE use aiohttp for this
    "summary": None,  # str The summary of the alliance
    "registered": False,
    "creation_date": None,
    "invite_url": None,
}

class MCOCCog(Commands, CDT, metaclass=CompositeMetaClass):
    """Marvel Contest of Champions"""

    __version__="3.0.0a"
    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_user(**default_user)
        self.config.register_global(**default_global)
        self.session = aiohttp.ClientSession
        self.default_user = default_user
    
    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())


    
