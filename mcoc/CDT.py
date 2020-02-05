from redbot.core import commands
import json
import aiohttp
import discord

# # For HashParser
# import modgrammar


class CDT(commands.Cog):
    """Library functions for CollectorDevTeam

    """

    ID = 3246316013445447780012
    COLLECTOR_ICON = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png'
    COLLECTOR_FEATURED = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/images/featured/collector.png'
    BASEPATH = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"
    PATREON = 'https://patreon.com/collectorbot'
    KABAM_ICON = 'https://imgur.com/UniRf5f.png'
    COLORS = {1: discord.Color(0x3c4d3b), 2: discord.Color(0xa05e44), 3: discord.Color(0xa0aeba),
                  4: discord.Color(0xe1b963), 5: discord.Color(0xf55738), 6: discord.Color(0x07c6ed),
                  'Cosmic': discord.Color(0x2799f7), 'Tech': discord.Color(0x0033ff),
                  'Mutant': discord.Color(0xffd400), 'Skill': discord.Color(0xdb1200),
                  'Science': discord.Color(0x0b8c13), 'Mystic': discord.Color(0x7f0da8),
                  'All': discord.Color(0x03f193), 'Superior': discord.Color(0x03f193),
                  'default': discord.Color.gold(), 'easy': discord.Color.green(),
                  'beginner': discord.Color.green(), 'medium': discord.Color.gold(),
                  'normal': discord.Color.gold(), 'heroic': discord.Color.red(),
                  'hard': discord.Color.red(), 'expert': discord.Color.purple(),
                  'master': discord.Color.purple(), 'epic': discord.Color(0x2799f7),
                  'uncollected': discord.Color(0x2799f7), 'symbiote': discord.Color.darker_grey(),
                  }

    # def _init__(self):
    #     pass

    def cdt_embed(self, ctx=None):
        """Discord Embed constructor with CollectorDevTeam defaults."""
        emauthor_icon_url = CDT.COLLECTOR_ICON
        if ctx is not None:
            emcolor = ctx.message.author.color
            emauthor = "Requested by {0.display_name} | {0.id}".format(ctx.message.author)
            emauthor_icon_url = ctx.message.author.avatar_url
        else:
            emcolor = discord.Color.gold()
            emauthor = "CollectorDevTeam"

        embed = discord.Embed(color=emcolor)
        embed.set_footer(text=emauthor, icon_url=emauthor_icon_url)
        return embed

    # @staticmethod
    async def fetch_json(self, ctx, url):
        ctx.send("Initializing 'fetch_json(ctx, url)'")
        async with aiohttp.ClientSession() as session:
            response = await session.get(url)
            raw_data = json.loads(await response.text())
        ctx.send("Returning json data")
        return raw_data
    
#
# ##################################################
# #  Hashtag grammar
# ##################################################
#
# class HashtagPlusError(TypeError):
#     pass
#
# class HashtagToken(modgrammar.Grammar):
#     grammar = modgrammar.WORD('#', "_a-zA-Z:*'0-9-"), modgrammar.WORD('_a-zA-Z:*0-9')
#
#     def match_set(self, roster):
#         return roster.raw_filtered_ids(set([self.string]))
#
#     def sub_aliases(self, aliases):
#         if self.string in aliases:
#             return '({})'.format(aliases[self.string])
#         else:
#             return self.string
#
#
# class HashParenExpr(modgrammar.Grammar):
#     grammar = (modgrammar.L('('), modgrammar.REF("HashExplicitSearchExpr"), modgrammar.L(")"))
#
#     def match_set(self, roster):
#         return self[1].match_set(roster)
#
#     def sub_aliases(self, aliases):
#         return '({})'.format(self[1].sub_aliases(aliases))
#
#
# class HashUnaryOperator(modgrammar.Grammar):
#     grammar = modgrammar.L('!')
#
#     def op(self, roster):
#         return roster.ids_set().difference
#
#
# class HashBinaryOperator(modgrammar.Grammar):
#     grammar = modgrammar.L('&') | modgrammar.L('|') | modgrammar.L('-') | modgrammar.L('+')
#
#     def op(self, roster):
#         if self.string == '&':
#             return set.intersection
#         elif self.string == '|':
#             return set.union
#         elif self.string == '-':
#             return set.difference
#         elif self.string == '+':
#             raise HashtagPlusError("Operator '+' is not defined for Hashtag Syntax")
#
#     def sub_aliases(self, aliases):
#         if self.string == '+':
#             raise HashtagPlusError("Operator '+' is not defined for Hashtag Syntax")
#         else:
#             return self.string
#
#
# class HashP0Term(modgrammar.Grammar):
#     grammar = (HashParenExpr | HashtagToken)
#
#     def match_set(self, roster):
#         return self[0].match_set(roster)
#
#     def sub_aliases(self, aliases):
#         return self[0].sub_aliases(aliases)
#
#
# class HashP0Expr(modgrammar.Grammar):
#     grammar = (HashUnaryOperator, HashP0Term)
#
#     def match_set(self, roster):
#         return self[0].op(roster)(self[1].match_set(roster))
#
#     def sub_aliases(self, aliases):
#         return self[0].string + self[1].sub_aliases(aliases)
#
#
# class HashP1Term(modgrammar.Grammar):
#     grammar = (HashP0Expr | HashParenExpr | HashtagToken)
#
#     def match_set(self, roster):
#         return self[0].match_set(roster)
#
#     def sub_aliases(self, aliases):
#         return self[0].sub_aliases(aliases)
#
#
# class HashP1Expr(modgrammar.Grammar):
#     grammar = (HashP1Term, modgrammar.ONE_OR_MORE(HashBinaryOperator, HashP1Term))
#
#     def match_set(self, roster):
#         matches = self[0].match_set(roster)
#         for e in self[1]:
#             matches = e[0].op(roster)(matches, e[1].match_set(roster))
#         return matches
#
#     def sub_aliases(self, aliases):
#         ret = self[0].sub_aliases(aliases)
#         for e in self[1]:
#             ret += e[0].sub_aliases(aliases) + e[1].sub_aliases(aliases)
#         return ret
#
#
# class HashExplicitSearchExpr(modgrammar.Grammar):
#     grammar = (HashP1Expr | HashP0Expr | HashParenExpr | HashtagToken)
#
#     def match_set(self, roster):
#         return self[0].match_set(roster)
#
#     def sub_aliases(self, aliases):
#         return self[0].sub_aliases(aliases)
#
#     def filter_roster(self, roster):
#         filt_ids = self.match_set(roster)
#         filt_roster = roster.filtered_roster_from_ids(filt_ids)
#         return filt_roster
#
#
# class HashImplicitSearchExpr(modgrammar.Grammar):
#     grammar = modgrammar.ONE_OR_MORE(HashtagToken, collapse=True)
#
#     def match_set(self, roster):
#         filt_ids = roster.ids_set()
#         for token in self:
#             filt_ids = filt_ids.intersection(token.match_set(roster))
#         return filt_ids
#
#     def sub_aliases(self, aliases):
#         ret = [token.sub_aliases(aliases) for token in self]
#         return ' & '.join(ret)
#
#
# class HashAttrSearchExpr(modgrammar.Grammar):
#     grammar = (modgrammar.OPTIONAL(AttrExpr),
#                modgrammar.OPTIONAL(HashImplicitSearchExpr | HashExplicitSearchExpr),
#                modgrammar.OPTIONAL(AttrExpr))
#
#     def sub_aliases(self, ctx, aliases):
#         attrs = self[0].get_attrs() if self[0] else {}
#         attrs = self[2].get_attrs(attrs) if self[2] else attrs
#         return (attrs, self[1].sub_aliases(aliases)) if self[1] else (attrs, '')
#
# class HashUserSearchExpr(modgrammar.Grammar):
#     grammar = (modgrammar.OPTIONAL(UserExpr),
#                modgrammar.OPTIONAL(HashImplicitSearchExpr | HashExplicitSearchExpr))
#
#     def sub_aliases(self, ctx, aliases):
#         user = self[0].get_user(ctx) if self[0] else ctx.message.author
#         return (user, self[1].sub_aliases(aliases)) if self[1] else (user, '')
#
#
# class HashParser:
#
#     def __init__(self): #, bot):
#         # self.bot = bot
#         self.attr_parser = HashAttrSearchExpr.parser()
#         self.user_parser = HashUserSearchExpr.parser()
#         self.explicit_parser = HashExplicitSearchExpr.parser()
#
#     async def parse_1st_pass(self, ctx, parser, hargs, aliases=None):
#         try:
#             result1 = parser.parse_string(hargs)
#         except modgrammar.ParseError as e:
#             await self.generic_syntax_error_msg(hargs, e)
#             raise
#         try:
#             return result1.sub_aliases(ctx, aliases)
#         except HashtagPlusError as e:
#             await self.hashtag_plus_error_msg()
#             raise
#
#     async def parse_2nd_pass(self, roster, expl_hargs):
#         if expl_hargs:
#             try:
#                 result2 = self.explicit_parser.parse_string(expl_hargs)
#             except modgrammar.ParseError as e:
#                 await self.generic_syntax_error_msg(hargs, e)
#                 return
#             try:
#                 return result2.filter_roster(roster)
#             except HashtagPlusError as e:
#                 await self.hashtag_plus_error_msg()
#                 return
#         else:
#             return roster
#
#     async def parse_with_attr(self, ctx, hargs, roster_cls, aliases=None):
#         '''Parser implies no user roster so use bot.  Parse attrs to pass to roster creation.'''
#         aliases = aliases if aliases else {}
#         try:
#             attrs, expl_hargs = await self.parse_1st_pass(ctx,
#                                 self.attr_parser, hargs, aliases)
#         except (HashtagPlusError, modgrammar.ParseError) as e:
#             #logger.info('SyntaxError caught ', str(e))
#             return
#         roster = roster_cls(ctx.bot, ctx.bot.user, attrs=attrs)
#         return await self.parse_2nd_pass(roster, expl_hargs)
#
#     async def parse_with_user(self, ctx, hargs, roster_cls, aliases=None):
#         '''Parser implies user roster.'''
#         aliases = aliases if aliases else {}
#         try:
#             user, expl_hargs = await self.parse_1st_pass(ctx, self.user_parser,
#                                 hargs, aliases)
#         except (HashtagPlusError, modgrammar.ParseError) as e:
#             #logger.info('SyntaxError caught ', str(e))
#             return
#         roster = roster_cls(ctx.bot, user)
#         ## Temporarily disabled until loading functions can be addressed.
#         ## Loading will probably be using the new Config.get(self, identifier=user.id)
#         ## Frist I need to ident the user.
#         # await roster.load_champions()
#         return await self.parse_2nd_pass(roster, expl_hargs)
#
#     async def generic_syntax_error_msg(self, hargs, e=None):
#         em = discord.Embed(title='Input Error', description='Syntax problem',
#                 color=discord.Color.red())
#         em.add_field(name="Don't mix implicit and explicit operators",
#                 value=hargs)
#         await ctx.bot.send(embed=em)
#         return
#
#     async def hashtag_plus_error_msg(self):
#         em = discord.Embed(title='Input Error', description='Syntax problem',
#                 color=discord.Color.red())
#         em.add_field(name="`+` operator is not defined for hashtags.",
#                 value="You probably want the `|` operator.  Call "
#                       "`/help hashtags` for detailed syntax.")
#         await ctx.bot.send(embed=em)
#         return
#
#     async def filter_and_display(self, ctx, hargs, roster_cls, aliases=None):
#         filtered = await self.parse_with_attr(ctx, hargs, roster_cls, aliases)
#         if filtered:
#             await filtered.display()
#         elif filtered is not None:
#             await filtered.warn_empty_roster(hargs)
#
#
# ##################################################
# #  End Grammar definitions
# ##################################################