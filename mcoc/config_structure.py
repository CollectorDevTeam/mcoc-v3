

config_structure = {
    "default_user" : {
        "profile": {
            "roster" : [], # List of champion dict
            "roster_screenshots": [],
            "alliance_ids": [],
            "started": None,
            "ingame": None,
            "aq5_paths":[],
            "aq6_paths":[],
            "aq7_paths":[],
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
        },
    },
    "default_guild": {
        "settings" : {},
    },

    "alliance_registry" : {
        "family" : {},
        "alliances" : {},
    },
    "mcoc" : {
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
} #end config structure
