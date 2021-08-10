from logging import exception, raiseExceptions
from ..abc import MixinMeta, commands, Context
from .cdtembed import Embed


CDTGUILD = 215271081517383682
COLLECTORDEVTEAM = 390253643330355200
COLLECTORSUPPORTTEAM = 390253719125622807
GUILDOWNERS = 391667615497584650
FAMILYOWNERS = 731197047562043464
PATRONS = 408414956497666050
CREDITED_PATRONS = 428627905233420288
CDTBOOSTERS = 736631216035594302
TATTLETALES = 537330789332025364

AUTHORIZATION = "Authorized as {0.mention}: {1}\n"
UNAUTHORIZED_GENERIC = "No."
UNAUTHORIZED_CDT = "This command is reserved for {0.mention}"
UNAUTHORIZED_GUILDOWNERS = "Sorry sweetheart.  These commands are reserved for **registered** {0.mention} only.\nIf you own or operate a guild, visit CDT and register."
UNAUTHORIZED_SUPPORTERS = "This command is reserved for Collector supporters.\n"  \
    "<:NitroBoost:870692021004812379>CDT {0.mention} get access to Perks chat & beta commands.\n"  \
    "<:patreon:548632991367168000>{1.mention} & {2.mention} get access to perks chat & beta commands.\n"

# class CdtCheck(CogCommandMixin):
class CdtCheck(MixinMeta):
    """Tools to check priveleges from CDT guild"""


    async def cdtcheck(ctx: Context , role_id):
        """Check for privileged role from CDT guild"""
        cdtguild = ctx.bot.get_guild(CDTGUILD)
        member = cdtguild.get_member(ctx.author.id)
        try:
            checkrole = cdtguild.get_role(role_id)
        except:
            raise "role not found"
            # raise MODOKError("cdtcheck: role {} not found!".format(role_id)) 
        result = False
        if member is not None and checkrole in member.roles:
            result = True
        return result, checkrole
        
    def is_collectordevteam():
        """Message caller is CollectorDevTeam"""
        async def pred(ctx: Context):
            chk, role = await CdtCheck.cdtcheck(ctx, COLLECTORDEVTEAM)
            msg = AUTHORIZATION.format(role, chk)
            allowed=False
            if chk:
                allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)
    
    def is_collectorsupportteam():
        """Message caller has CollectorSupportTeam or CollectorDevTeam on CDT"""
        async def pred(ctx: Context):
            allowed=False
            msg = ""
            for rid in (COLLECTORSUPPORTTEAM, COLLECTORDEVTEAM):
                chk, role = await CdtCheck.cdtcheck(ctx, rid)
                msg += AUTHORIZATION.format(role, chk)
            if chk:
                allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    def is_guildowners():
        """Message caller has GuildOwners role on CDT"""
        async def pred(ctx: Context):
            chk, role = await CdtCheck.cdtcheck(ctx, GUILDOWNERS)
            msg = AUTHORIZATION.format(role, chk)
            allowed=False
            if chk:
                allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    def is_familyowners():
        """Message caller has FamilyOwners role on CDT"""
        async def pred(ctx: Context):
            chk, role = await CdtCheck.cdtcheck(ctx, FAMILYOWNERS)
            msg = AUTHORIZATION.format(role, chk)
            allowed=False
            if chk:
                allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    def is_patron():
        """Message caller has Patron role on CDT"""
        async def pred(ctx: Context):
            for rid in (PATRONS, CREDITED_PATRONS):
                chk, role = await CdtCheck.cdtcheck(ctx, rid)
                msg = AUTHORIZATION.format(role, chk)
                allowed=False
                if chk:
                    allowed=chk
                if not allowed:
                    await CdtCheck.tattle(ctx, message=msg)
                return bool(allowed)
        return commands.check(pred)

    def is_booster():
        """Message caller has Server Booster role on CDT"""
        async def pred(ctx: Context):
            chk, role = await CdtCheck.cdtcheck(ctx, CDTBOOSTERS)
            msg = AUTHORIZATION.format(role, chk)
            allowed=False
            if chk:
                allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    def is_supporter():
        """Message caller has a supporter role: CDT Booster, Patrons, Credited Patrons"""
        async def pred(ctx: Context):
            msg =""
            allowed=False
            for rid in (CDTBOOSTERS, PATRONS, CREDITED_PATRONS):
                chk, role = await CdtCheck.cdtcheck(ctx, rid)
                msg += AUTHORIZATION.format(role, chk)
                if chk:
                    allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    
    def is_any_priviledged():
        """Message caller has a supporter role: CDT Booster, Patrons, Credited Patrons"""
        async def pred(ctx: Context):
            msg =""
            allowed=False
            for rid in (CDTBOOSTERS, PATRONS, CREDITED_PATRONS, COLLECTORDEVTEAM, COLLECTORSUPPORTTEAM):
                chk, role = await CdtCheck.cdtcheck(ctx, rid)
                msg += AUTHORIZATION.format(role, chk)
                if chk:
                    allowed=chk
            if not allowed:
                await CdtCheck.tattle(ctx, message=msg)
            return bool(allowed)
        return commands.check(pred)

    async def tattle(ctx, message="User is unauthorized.", channel=None):
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