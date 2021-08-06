from .abc import MixinMeta
import discord

class Branding(MixinMeta):
    PATREON = 'https://www.patreon.com/collectorbot'
    JJW_TIPJAR = ''
    COLLECTOR_SQUINT = "https://cdn.discordapp.com/attachments/391330316662341632/867885227603001374/collectorbota.gif"
    COLLECTOR_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
    CDTLOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
    CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
    ASSET_BASEPATH = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"




class Emoji(MixinMeta):
    """discord emoji

    Args:
        MixinMeta ([type]): [description]
    """
    emoji = {
        "nitroboost" : "<:NitroBoost:870692021004812379>",
        "Cosmic": "<:cosmic:748808707328180265>", 
        "Tech": "<:tech:748808546283683870>",
        "Mutant": "<:mutant:748808841465954304>",
        "Skill": "<:skill:748809095456227389>",
        "Science": "<:science:748809185398882404>",
        "Mystic": "<:mystic:748808953701335080>",
        "All": "<:allclasses:748808348996075540>",
        "Superior": "<:allclasses:748808348996075540>",
        "default": "",
        }

class CDTColor(MixinMeta):
    
    COLORCOSMIC = discord.Color(0x2799f7)
    COLORTECH = discord.Color(0x0033ff)
    COLORMUTANT = discord.Color(0xffd400)
    COLORSKILL = discord.Color(0xdb1200)
    COLORSCIENCE = discord.Color(0x0b8c13)
    COLORMYSTIC = discord.Color(0x7f0da8)
    COLORALL = discord.Color(0x03f193)
    COLORCOLLECTOR = discord.Color.gold()
    COLORDEFAULT = discord.Color.light_grey()

    ClassColors = {
        "Cosmic": COLORCOSMIC, 
        "Tech": COLORTECH,
        "Mutant": COLORMUTANT, 
        "Skill": COLORSKILL,
        "Science": COLORSCIENCE, 
        "Mystic": COLORMYSTIC,
        "All": COLORALL, 
        "Superior": COLORALL, 
        "default": COLORDEFAULT,
    }