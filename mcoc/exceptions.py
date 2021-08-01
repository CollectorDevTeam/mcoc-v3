from .abc import MixinMeta
from redbot.core import commands
from .cdtcore import CDT
import random
import discord

remote_data_basepath = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"

MODOKSAYS = ['alien', 'buffoon', 'charlatan', 'creature', 'die', 'disintegrate',
        'evaporate', 'feelmypower', 'fool', 'fry', 'haha', 'iamscience', 'idiot',
        'kill', 'oaf', 'peabrain', 'pretender', 'sciencerules', 'silence',
        'simpleton', 'tincan', 'tremble', 'ugh', 'useless']

class MODOKException(Exception):
    pass

class QuietUserError(commands.UserInputError):
    pass

class AmbiguousArgError(QuietUserError):
    pass

class MODOKError(QuietUserError):
    pass

class MODOKSays(MixinMeta):
    def raw_modok_image():
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(remote_data_basepath, word)
        return modokimage
    
    async def raw_modok_says(self, ctx):
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(remote_data_basepath, word)
        print(modokimage)
        data = await CDT.create_embed(ctx, color=discord.Color(0x0b8c13), title="M.O.D.O.K. says", image=modokimage)
        data.set_thumbnail(url="")
        await ctx.send(embed=data)




