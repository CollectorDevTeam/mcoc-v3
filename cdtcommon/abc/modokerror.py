from redbot.core import commands
from cdtcommon.abc.cdtembed import Embed
import random
from typing import Optional
import discord

remote_data_basepath = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"

MODOKSAYS = ['alien', 'buffoon', 'charlatan', 'creature', 'die', 'disintegrate',
        'evaporate', 'feelmypower', 'fool', 'fry', 'haha', 'iamscience', 'idiot',
        'kill', 'oaf', 'peabrain', 'pretender', 'sciencerules', 'silence',
        'simpleton', 'tincan', 'tremble', 'ugh', 'useless']

class QuietUserError(commands.UserInputError):
    pass

class AmbiguousArgError(QuietUserError):
    pass

class MODOKError(QuietUserError):
    pass

async def raw_modok_says(ctx, channel: Optional [discord.Message.channel], word=None):
    if not word or word not in MODOKSAYS:
        word = random.choice(MODOKSAYS)
    modokimage = "{}images/modok/{}.png".format(remote_data_basepath, word)
    data = Embed.create_embed(ctx, color=discord.Color(0x0b8c13), title="M.O.D.O.K. says", image=modokimage)
    channel.send(embed=data)


