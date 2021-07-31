from cdtcommon.abc.mixin import cdtcommands
from cdtcommon.abc.abc import MixinMeta
from cdtcommon.abc.cdt import CDT
import math
import re

import discord
from redbot.core import commands

CALC_THUMBNAIL = "https://www.ebuyer.com/blog/wp-content/uploads/2014/07/buttons-on-a-calculator-header1.jpg"
class CDTCalculator(MixinMeta):
    """Calculator"""

    # def __init__(self, bot):
    #     self.bot = bot
    #     self.thumbnail 

    @cdtcommands.group(name="calculator", aliases=("calc",))
    async def cdt_calc(self, ctx, m=None):
        """Math is fun!
        Type math, get fun."""
        # m = "".join(m)
        math_filter = re.findall(
            r"[\[\]\-()*+/0-9=.,% ]|>|<|==|>=|<=|\||&|~|!=|^|sum"
            + "|range|random|randint|choice|randrange|True|False|if|and|or|else"
            + "|is|not|for|in|acos|acosh|asin|asinh|atan|atan2|atanh|ceil"
            + "|copysign|cos|cosh|degrees|e|erf|erfc|exp|expm1|fabs|factorial"
            + "|floor|fmod|frexp|fsum|gamma|gcd|hypot|inf|isclose|isfinite"
            + "|isinf|isnan|ldexp|lgamma|log|log10|log1p|log2|modf|nan|pi"
            + "|pow|radians|sin|sinh|sqrt|tan|tanh|round",
            m,
        )
        calculate_stuff = eval("".join(math_filter))
        if len(str(calculate_stuff)) > 0:
            em = await CDT.create_embed(
                ctx,
                title="CollectorDevTeam Calculator",
                description="**Input**\n`{}`\n\n**Result**\n`{}`".format(m, calculate_stuff),
            )
            em.add_field(name="Type Math", value="Get Fun")
            await ctx.send(embed=em)

    @cdt_calc.command(aliases=("p2f","\%\2f"),)
    async def per2flat(self, ctx, per: float, ch_rating: int = 100):
        """Convert Percentage to MCOC Flat Value"""
        await ctx.send(CDT.to_flat(per, ch_rating))

    # , aliases=('f2p')) --> this was translating as "flat | f | 2 | p"
    @cdt_calc.command(pass_context=True, name="flat")
    async def flat2per(self, ctx, *, m):
        """Convert MCOC Flat Value to Percentge
        <equation> [challenger rating = 100]"""
        if "cr" in m:
            m, cr = m.rsplit("cr", 1)

        elif " " in m:
            m, cr = m.rsplit(" ", 1)
            challenger_rating = int(cr)
        else:
            challenger_rating = 100
        m = "".join(m)
        # cr_filter = re.findall(
        #     r""
        # )
        math_filter = re.findall(
            r"[\[\]\-()*+/0-9=.,% ]"
            + r"|acos|acosh|asin|asinh"
            + r"|atan|atan2|atanh|ceil|copysign|cos|cosh|degrees|e|erf|erfc|exp"
            + r"|expm1|fabs|factorial|floor|fmod|frexp|fsum|gamma|gcd|hypot|inf"
            + r"|isclose|isfinite|isinf|isnan|round|ldexp|lgamma|log|log10|log1p"
            + r"|log2|modf|nan|pi|pow|radians|sin|sinh|sqrt|tan|tanh",
            m,
        )
        flat_val = eval("".join(math_filter))
        p = CDT.from_flat(flat_val, challenger_rating)
        data = await CDT.create_embed(
            ctx,
            title="FlatValue:",
            thumbnail=CALC_THUMBNAIL,
            description="{}".format(flat_val),
        )
        data.add_field(name="Percentage:", value="{}\%".format(p))
        await ctx.send(embed=data)

    @cdt_calc.command(aliases=["compf", "cfrac"], hidden=True)
    async def compound_frac(self, ctx, base: float, exp: int):
        # On second thought, I'm not gonna touch this
        # - Jojo
        """Calculate multiplicative compounded fractions"""
        if base > 1:
            base = base / 100
        compound = 1 - (1 - base) ** exp
        data = await CDT.create_embed(
            ctx,
            color=discord.Color.gold(),
            title="Compounded Fractions",
            thumbnail=CALC_THUMBNAIL,
            description="{:.2%} compounded {} times".format(base, exp),
        )
        data.add_field(name="Expected Chance", value="{:.2%}".format(compound))
        await ctx.send(embed=data)
