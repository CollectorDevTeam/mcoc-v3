import discord
from redbot.core import commands, checks
from redbot.core.config import Config
from .cdtembed import Embed
from .cdtcommon import CdtCommon
import math
import re


class Calculator(commands.Cog):
    """Calculator"""

    def __init__(self, bot):
        self.bot = bot
        self.Embed = Embed(self)
        self.thumbnail = "https://www.ebuyer.com/blog/wp-content/uploads/2014/07/buttons-on-a-calculator-header1.jpg"

    @commands.command(pass_context=True, name='calculator', aliases=('calc',))
    async def _calc(self, ctx, *, m):
        """Math is fun!
        Type math, get fun."""
        m = ''.join(m)
        math_filter = re.findall(r'[\[\]\-()*+/0-9=.,% ]|>|<|==|>=|<=|\||&|~|!=|^|sum'
                                 + '|range|random|randint|choice|randrange|True|False|if|and|or|else'
                                 + '|is|not|for|in|acos|acosh|asin|asinh|atan|atan2|atanh|ceil'
                                 + '|copysign|cos|cosh|degrees|e|erf|erfc|exp|expm1|fabs|factorial'
                                 + '|floor|fmod|frexp|fsum|gamma|gcd|hypot|inf|isclose|isfinite'
                                 + '|isinf|isnan|ldexp|lgamma|log|log10|log1p|log2|modf|nan|pi'
                                 + '|pow|radians|sin|sinh|sqrt|tan|tanh|round', m)
        try:
            calculate_stuff = eval(''.join(math_filter))
        except NameError:
            calculate_stuff = 0
        if len(str(calculate_stuff)) > 0:
            em = self.Embed.create(ctx, title="CollectorDevTeam Calculator",
                                   thumbnail=self.thumbnail,
                                   description='**Input**\n`{}`\n\n**Result**\n`{}`'.format(m, calculate_stuff))
            em.add_field(name="Type Math", value="Get Fun")
            await ctx.send(embed=em)
        else:
            await ctx.send("Hm, it looks like that wasn't a valid calculation")

    @commands.command(pass_context=True, aliases=['p2f', ], hidden=True)
    async def per2flat(self, ctx, per: float, ch_rating: int = 100):
        '''Convert Percentage to MCOC Flat Value'''
        await ctx.send(CdtCommon.to_flat(per, ch_rating))

    # , aliases=('f2p')) --> this was translating as "flat | f | 2 | p"
    @commands.command(pass_context=True, name='flat')
    async def flat2per(self, ctx, *, m):
        '''Convert MCOC Flat Value to Percentge
        <equation> [challenger rating = 100]'''
        if ' ' in m:
            m, cr = m.rsplit(' ', 1)
            challenger_rating = int(cr)
        else:
            challenger_rating = 100
        m = ''.join(m)
        math_filter = re.findall(r'[\[\]\-()*+/0-9=.,% ]' +
                                 r'|acos|acosh|asin|asinh' +
                                 r'|atan|atan2|atanh|ceil|copysign|cos|cosh|degrees|e|erf|erfc|exp' +
                                 r'|expm1|fabs|factorial|floor|fmod|frexp|fsum|gamma|gcd|hypot|inf' +
                                 r'|isclose|isfinite|isinf|isnan|round|ldexp|lgamma|log|log10|log1p' +
                                 r'|log2|modf|nan|pi|pow|radians|sin|sinh|sqrt|tan|tanh', m)
        flat_val = eval(''.join(math_filter))
        p = CdtCommon.from_flat(flat_val, challenger_rating)
        em = self.Embed.create(ctx, color=discord.Color.gold(),
                               title='FlatValue:',
                               thumbnail=self.thumbnail,
                               description='{}'.format(flat_val))
        em.add_field(name='Percentage:', value='{}\%'.format(p))
        await ctx.send(embed=em)

    @commands.command(pass_context=True, aliases=['compf', 'cfrac'], hidden=True)
    async def compound_frac(self, ctx, base: float, exp: int):
        '''Calculate multiplicative compounded fractions'''
        if base > 1:
            base = base / 100
        compound = 1 - (1 - base)**exp
        em = self.Embed.create(ctx, color=discord.Color.gold(),
                               title="Compounded Fractions",
                               thumbnail=self.thumbnail,
                               description='{:.2%} compounded {} times'.format(base, exp))
        em.add_field(name='Expected Chance', value='{:.2%}'.format(compound))
        await ctx.send(embed=em)
