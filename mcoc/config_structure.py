

config_structure = {
    "default_user" : {
        "profile": {
            "description" : None, #string < 1000
            "roster" : [], # List of champion dict
            "roster_ss": [],
            "alliance_ids": [], #list of dicts { alliance: 1234, tag: ABCDE}
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
        "champions": {}, # Champion Class registry 
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
    }, # end global set,
    "default_champion" :  {
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
} #end config structure
