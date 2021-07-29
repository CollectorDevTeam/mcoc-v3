from redbot.core import commands, Config
from redbot.core.bot import Red
from abc import ABC

from redbot.core.commands.commands import CogCommandMixin

from cdtcommon.cdtembed import Embed


class CdtCheck(CogCommandMixin):
    def __init__(self, *_args):
        self.config: Config
        self.bot: Red
    
        self.CDTGUILD = 215271081517383682
        self.COLLECTORDEVTEAM = 390253643330355200
        self.COLLECTORSUPPORTTEAM = 390253719125622807
        self.GUILDOWNERS = 391667615497584650
        self.FAMILYOWNERS = 731197047562043464
        self.PATRONS: 408414956497666050
        self.CREDITED_PATRONS: 428627905233420288
        self.CDTBOOSTERS = 736631216035594302
        self.TATTLETALES = 537330789332025364

    async def cdtcheck(self, ctx, role_id):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(self.CDTGUILD)
        checkrole = cdtguild.get_role(role_id)
        member = cdtguild.get_member(ctx.author.id)
        if member is None:
            return False
        elif checkrole in member.roles:
            return True
        else:
            return True

    def is_collectordevteam():
        async def pred(ctx: commands.Context):
            checkrole = CdtCheck.COLLECTORDEVTEAM
            chk = CdtCheck.cdtcheck(ctx, checkrole)
            if not chk:
                await CdtCheck.tattle(ctx, message="User is not authorized")
        return commands.check(pred)
    
    def is_collectorsupportteam():
        async def pred(ctx: commands.Context):
            checkrole = CdtCheck.COLLECTORSUPPORTTEAM
            chk = CdtCheck.cdtcheck(ctx, checkrole)
            if not chk:
                await CdtCheck.tattle(ctx, message="User is not authorized")
        return commands.check(pred)

    def is_guildowners():
        async def pred(ctx: commands.Context):
            checkrole = CdtCheck.GUILDOWNERS
            chk = CdtCheck.cdtcheck(ctx, checkrole)
            if not chk:
                await CdtCheck.tattle(ctx, message="User is not authorized")
        return commands.check(pred)

    def is_familyowners():
        async def pred(ctx: commands.Context):
            checkrole = CdtCheck.FAMILYOWNERS
            chk = CdtCheck.cdtcheck(ctx, checkrole)
            if not chk:
                await CdtCheck.tattle(ctx, message="User is not authorized")
        return commands.check(pred)

    def is_supporter():
        async def pred(ctx: commands.Context):
            booster = await CdtCheck.cdtcheck(ctx, CdtCheck.CDTBOOSTERS)
            patron = await CdtCheck.cdtcheck(ctx, CdtCheck.PATRONS)
            credited_patron = await CdtCheck.cdtcheck(ctx, CdtCheck.CREDITED_PATRONS)
            if not (booster or patron or credited_patron):
                await CdtCheck.tattle(ctx, message="User is not authorized")
        return commands.check(pred)

    async def tattle(ctx, message, channel=None):
        """"Someone's been a naughty boy/girl/it/zey/zim"""
        cdtguild = ctx.bot.get_guild(CdtCheck.CDTGUILD)
        if channel is None:
            channel=cdtguild.get_channel(CdtCheck.TATTLETALES)
        data = Embed.create(title="CDT Tattletales", description=message)
        data.add_field(name="Who", value="{ctx.author.name} [{ctx.author.id}]")
        data.add_field(name="What", value="{ctx.message.content}")
        data.add_field(name="Where", value="{ctx.guild.name} [{ctx.guild.id}]")
        data.add_field(name="When", value="{ctx.timestamp}")
        await ctx.bot.send(embed=data, channel=channel)
        return
