from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdt_core import CDT
from ..exceptions import MODOKError, MODOKException

import random


MODOKSAYS = ['alien', 'buffoon', 'charlatan', 'creature', 'die', 'disintegrate',
        'evaporate', 'feelmypower', 'fool', 'fry', 'haha', 'iamscience', 'idiot',
        'kill', 'oaf', 'peabrain', 'pretender', 'sciencerules', 'silence',
        'simpleton', 'tincan', 'tremble', 'ugh', 'useless']

class MODOKSays(MixinMeta, metaclass=CompositeMetaClass):
    def raw_modok_image():
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(CDT.ASSET_BASEPATH, word)
        return modokimage
    
    async def raw_modok_says(self, ctx: Context):
        word = random.choice(MODOKSAYS)
        modokimage = "{}images/modok/{}.png".format(CDT.ASSET_BASEPATH, word)
        modokthumbnail = "{}images/portraits/modok.png".format(CDT.ASSET_BASEPATH)
        print(modokimage)
        data = await CDT.create_embed(ctx, color=CDT.COLORSCIENCE, title="M.O.D.O.K. says", image=modokimage, thumbnail=None, description='')
        await ctx.send(embed=data)

    @commands.command(name="modok", hidden=True)
    async def modoksays(self, ctx: Context):
        await self.raw_modok_says(ctx)

    # @commands.command()
    # async def modokexception(self, ctx: Context):
    #     raise MODOKException("TEST!")

    # @commands.command()
    # async def modokerror(self, ctx: Context):
    #     raise MODOKError("This is an error!")