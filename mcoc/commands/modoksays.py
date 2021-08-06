from .abc import MixinMeta
from .abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass, CDT, mcocgroup

import random
import discord


MODOKSAYS = ['alien', 'buffoon', 'charlatan', 'creature', 'die', 'disintegrate',
        'evaporate', 'feelmypower', 'fool', 'fry', 'haha', 'iamscience', 'idiot',
        'kill', 'oaf', 'peabrain', 'pretender', 'sciencerules', 'silence',
        'simpleton', 'tincan', 'tremble', 'ugh', 'useless']

class MODOKSays(MixinMeta):
    def raw_modok_image():
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(CDT.ASSET_BASEPATH, word)
        return modokimage
    
    async def raw_modok_says(self, ctx: Context):
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(CDT.ASSET_BASEPATH, word)
        print(modokimage)
        data = await CDT.create_embed(ctx, color=CDT.COLORSCIENCE, title="M.O.D.O.K. says", image=modokimage)
        data.set_thumbnail(url="")
        await ctx.send(embed=data)