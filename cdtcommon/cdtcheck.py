from redbot.core import commands, Config
from redbot.core.bot import Red
from abc import ABC

from redbot.core.commands.commands import CogCommandMixin

from cdtcommon.cdtembed import Embed

CDTGUILD = 215271081517383682
COLLECTORDEVTEAM = 390253643330355200
COLLECTORSUPPORTTEAM = 390253719125622807
GUILDOWNERS = 391667615497584650
FAMILYOWNERS = 731197047562043464
PATRONS: 408414956497666050
CREDITED_PATRONS: 428627905233420288
CDTBOOSTERS = 736631216035594302
TATTLETALES = 537330789332025364
class CdtCheck(CogCommandMixin):
    def __init__(self, *_args):
        self.config: Config
        self.bot: Red
    


    async def cdtcheck(ctx, role_ids:list):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        member = cdtguild.get_member(ctx.author.id)
        if member is None:
            await CdtCheck.tattle(ctx, message="User is not member on CDT")
            return False
        for role_id in role_ids:
            checkrole = cdtguild.get_role(role_id)
            if checkrole in member.roles:
                await CdtCheck.tattle(ctx, message="User is authorized as **{0}**".format(checkrole.mention))
                return True
            else:
                await CdtCheck.tattle(ctx, message="User is not authorized!")
                return False
            

    def is_collectordevteam():
        async def pred(ctx: commands.Context):
            checkrole = [COLLECTORDEVTEAM]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)
    
    def is_collectorsupportteam():
        async def pred(ctx: commands.Context):
            checkrole = [COLLECTORSUPPORTTEAM, COLLECTORDEVTEAM]
            chk = await  CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_guildowners():
        async def pred(ctx: commands.Context):
            checkrole = [GUILDOWNERS]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_familyowners():
        async def pred(ctx: commands.Context):
            checkrole = [FAMILYOWNERS]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_supporter():
        async def pred(ctx: commands.Context):
            checkrole = [CDTBOOSTERS, PATRONS, CREDITED_PATRONS, COLLECTORSUPPORTTEAM, COLLECTORDEVTEAM]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    async def tattle(ctx, message, channel=None):
        """"Someone's been a naughty boy/girl/it/zey/zim"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        if channel is None:
            channel=cdtguild.get_channel(TATTLETALES) #default to tattletales
        data = await Embed.create(ctx, title="CDT Tattletales", description=message)
        data.add_field(name="Who", value="{0.name} [{0.id}]".format(ctx.author))
        data.add_field(name="What", value="{0.content}".format(ctx.author))
        data.add_field(name="Where", value="{0.name} [{0.id}]".format(ctx.author))
        data.add_field(name="When", value="{0}".format(ctx.author))
        await channel.send(embed=data)
        return
