import discord
from redbot.core import checks, commands
from redbot.core.bot import Red

from typing import List, Iterable, Union

COLLECTORDEVTEAM = "390253643330355200"
COLLECTORSUPPORTTEAM = "390253719125622807"
GUILDOWNERS = "391667615497584650"
FAMILYOWNERS = "731197047562043464"

async def is_collectordevteam(
    bot: "Red", obj: Union[discord.Message, discord.Member]
):
    guild =  bot.get_guild(215271081517383682)
    cdt = None
    for r in guild.roles:
        if r.id is 390253643330355200:
            cdt = r
            continue

    if isinstance(obj, discord.Message):
        user = obj.author
    elif isinstance(obj, discord.Member):
        user = obj
    elif isinstance(obj, discord.User):
        user = obj
    else:
        raise TypeError("Only messages, members or uers may be passed")

    member = await bot.get_or_fetch_member(guild, user.id)
    if member is None:
        print("bot did not get_or_fetch_member")
        return False
    elif cdt in member.roles:
        print("cdt in member.roles")
        return True
    else: 
        print("cdt role not in member.roles")
        return False
