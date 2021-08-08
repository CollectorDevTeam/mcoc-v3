

config_structure = {
    "default_user" : {
        "profile": {
            "description" : None, #string < 1000
            "roster" : [], # List of champion dict
            "roster_ss": [],
            "alliance_ids": [],
            "alliance_tag": None,
            "started": None,
            "ingame": None,
            "aq5_paths":[],
            "aq6_paths":[],
            "aq7_paths":[],
            "aw": [],
            "offense": None,
            "defense": None,
            "utility": None,
            "collage": None,
        },
        "settings": {
            "auntmai": None, #str auntmai key,
            "hide_t1" : False,
            "hide_t2" : False,
            "hide_t3" : False,
            "hide_t4" : False,
            "hide_t5" : False,
            "hide_t6" : False,    
            
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
