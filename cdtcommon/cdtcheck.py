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
    


    async def cdtcheck(ctx, role_id):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        checkrole = cdtguild.get_role(role_id)
        member = cdtguild.get_member(ctx.author.id)
        if member is None:
            await CdtCheck.tattle(ctx, message="User is not member on CDT")
            return False
        elif checkrole in member.roles:
            await CdtCheck.tattle(ctx, message="User is authorized")
            return True
        else:
            await CdtCheck.tattle(ctx, message="User is not authorized")
            return False
            

    def is_collectordevteam():
        async def pred(ctx: commands.Context):
            checkrole = COLLECTORDEVTEAM
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)
    
    def is_collectorsupportteam():
        async def pred(ctx: commands.Context):
            checkrole = COLLECTORSUPPORTTEAM
            chk = await  CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_guildowners():
        async def pred(ctx: commands.Context):
            checkrole = GUILDOWNERS
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_familyowners():
        async def pred(ctx: commands.Context):
            checkrole = FAMILYOWNERS
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_supporter():
        async def pred(ctx: commands.Context):
            booster = await CdtCheck.cdtcheck(ctx, CDTBOOSTERS)
            patron = await CdtCheck.cdtcheck(ctx, PATRONS)
            credited_patron = await CdtCheck.cdtcheck(ctx, CREDITED_PATRONS)
            if booster or patron or credited_patron:
                return True
            else:
                return False
        return commands.check(pred)

    async def tattle(ctx, message, channel=None):
        """"Someone's been a naughty boy/girl/it/zey/zim"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        if channel is None:
            channel=cdtguild.get_channel(TATTLETALES) #default to tattletales
        data = await Embed.create(ctx, title="CDT Tattletales", description=message)
        data.add_field(name="Who", value="{ctx.author.name} [{ctx.author.id}]")
        data.add_field(name="What", value="{ctx.message.content}")
        data.add_field(name="Where", value="{ctx.guild.name} [{ctx.guild.id}]")
        data.add_field(name="When", value="{ctx.timestamp}")
        await ctx.bot.send(embed=data, channel=channel)
        return
