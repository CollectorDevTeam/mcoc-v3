from cdtcommon.abc.abc import MixinMeta
from cdtcommon.abc.cdtembed import Embed
from redbot.core import commands

CDTGUILD = 215271081517383682
COLLECTORDEVTEAM = 390253643330355200
COLLECTORSUPPORTTEAM = 390253719125622807
GUILDOWNERS = 391667615497584650
FAMILYOWNERS = 731197047562043464
PATRONS: 408414956497666050
CREDITED_PATRONS: 428627905233420288
CDTBOOSTERS = 736631216035594302
TATTLETALES = 537330789332025364

# class CdtCheck(CogCommandMixin):
class CdtCheck(MixinMeta):
    """Tools to check priveleges from CDT guild"""
    # def __init__(self, *_args):
    #     self.config: Config
    #     self.bot: Red
    


    async def cdtcheck(ctx, role_ids:list):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        member = cdtguild.get_member(ctx.author.id)
        if member is None:
            await CdtCheck.tattle(ctx, message="User is not member on CDT")
            return False
        result = False
        checked_roles = []
        message = ""
        for role_id in role_ids:
            checkrole = cdtguild.get_role(role_id)
            checked_roles.append(checkrole)
            if checkrole in member.roles:
                message+="User is authorized as {0}.\n".format(checkrole.mention)
                result = True
            else:
                message+="User is not authorized as {0}!\n".format(checkrole.mention)
        
        await CdtCheck.tattle(ctx, message)
        return result
            

    def is_collectordevteam():
        """Message caller is CollectorDevTeam"""
        async def pred(ctx: commands.Context):
            checkrole = [COLLECTORDEVTEAM]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)
    
    def is_collectorsupportteam():
        """Message caller has CollectorSupportTeam or CollectorDevTeam on CDT"""
        async def pred(ctx: commands.Context):
            checkrole = [COLLECTORSUPPORTTEAM, COLLECTORDEVTEAM]
            chk = await  CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_guildowners():
        """Message caller has GuildOwners role on CDT"""
        async def pred(ctx: commands.Context):
            checkrole = [GUILDOWNERS]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_familyowners():
        """Message caller has FamilyOwners role on CDT"""
        async def pred(ctx: commands.Context):
            checkrole = [FAMILYOWNERS]
            chk = await CdtCheck.cdtcheck(ctx, checkrole)
            if chk:
                return chk
        return commands.check(pred)

    def is_supporter():
        """Message caller has a supporter role: CDT Booster, Patrons, Credited Patrons"""
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
        data = await Embed.create_embed(ctx, title="CDT Tattletales", description=message)
        data.add_field(name="Who", value="{0.mention}\n[{0.id}]".format(ctx.author), inline=False)
        data.add_field(name="What", value="```{0.content}```".format(ctx.message), inline=False)
        data.add_field(name="Where", value="{0.name} \nguild.id:   {0.id}\nmessage.id: [{1.id}]({1.jump_url})".format(ctx.guild, ctx.message), inline=False)
        data.add_field(name="When", value="{0.created_at}".format(ctx.message), inline=False)
        await channel.send(embed=data)
        return
