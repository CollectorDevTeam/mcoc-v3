import discord
from redbot.core import commands, checks
from redbot.core.config import Config
from redbot.core.utils import menus, chat_formatting
from .cdtembed import Embed


class CdtCommon(commands.Cog):
    """
    Common Files
    """

    def __init__(self, bot):
        self.bot = bot
        self.Embed = Embed(self)
        self.config = Config.get_conf(
            self,
            identifier=8675309,
            force_registration=True,
        )

    @commands.command(pass_context=True, no_pm=True)
    async def showtopic(self, ctx, channel: discord.TextChannel = None):
        """Show the Channel Topic in the chat channel as a CDT Embed."""
        if channel is None:
            channel = ctx.message.channel
        topic = channel.topic
        if topic is not None and topic != '':
            data = self.Embed.create(ctx, title='#{} Topic :sparkles:'.format(
                                     channel.name),
                                 description=topic)
            data.set_thumbnail(url=ctx.message.guild.icon_url)
            await ctx.send(embed=data)

    @commands.command(pass_context=True, name='list_members', aliases=('list_users',))
    async def _users_by_role(self, ctx, role: discord.Role, use_alias=True):
        '''Embed a list of server users by Role'''
        guild = ctx.message.guild
        pages = []
        members = self._list_users(ctx, role, ctx.message.guild)
        if members is not None:
            if use_alias is True:
                ret = '\n'.join('{0.display_name}'.format(m) for m in members)
            else:
                ret = '\n'.join('{0.name} [{0.id}]'.format(m) for m in members)
            pagified = chat_formatting.pagify(ret)
            # if use_alias:
            #     ret = '\n'.join([m.display_name for m in members])
            # else:
            #     ret = '\n'.join([m.name for m in members])
            for page in pagified:
                data = self.Embed.create(ctx, title='{0.name} Role - {1} member(s)'.format(role, len(members)),
                        description=page)
                pages.append(data)   
            if len(pages) == 1:
                await ctx.send(embed=data)
            # elif len(pages) > 1:
            #     await menus.menu(ctx=ctx, pages=pages, controls=self._get_controls(pages))


    def _list_users(self, ctx, role: discord.Role, guild: discord.guild):
        """Given guild and role, return member list"""
        members = []
        for member in guild.members:
            if role in member.roles:
                members.append(member)
        if len(members) > 0:
            return members
        else:
            return None

        
    def _get_controls(self, list: list, export: bool = False):
        controls = {}
        if len(list) < 5:
            controls.update({
                # "<:arrowsleft:735628703824085004>" : menus.prev_page,
                "<:arrowleft:735628703610044488>" : menus.prev_page,
                "<:circlex:735628703530483814>" : menus.close_menu, 
                "<:arrowright:735628703840600094>" : menus.next_page
                # "<:arrowsright:735628703609913396>": menus.next_page
            })
        elif len(list) >= 5:
            controls.update({
                "<:arrowsleft:735628703824085004>" : menus.prev_page,
                "<:arrowleft:735628703610044488>" : menus.prev_page,
                "<:circlex:735628703530483814>" : menus.close_menu, 
                "<:arrowright:735628703840600094>" : menus.next_page,
                "<:arrowsright:735628703609913396>": menus.next_page
            })
        if export is True:
            controls.update({"<:slow:735197282206482502>": close_menu})
        return controls
        
