from .abc import MixinMeta
from redbot.core.bot import Red 

    
cdt_emoji = {
    "nitroboost" : "<:NitroBoost:870692021004812379>",
    }

class CDTEmoji(MixinMeta):
    """class to return emoji strings"""

    emoji = cdt_emoji

    # def __init__(self, bot: Red):
    #     self.bot = bot
    #     self.emoji = set()

    # def update_emoji(self):
    #     for e  in cdt_emoji.keys():
    #         self.emoji.add()
    

    
    # for e in emoji.keys():
