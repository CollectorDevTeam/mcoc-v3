from .. import exceptions

from .abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass, CDT, mcocgroup

import discord
from typing import Union, Optional


GUILDOWNER_ONLY = "Only guild owners or guild administrators may execute this command."
OFFICER_ONLY = "Only Alliance Officers may set Alliance properties."
ALLIANCE_FOOTER = "CollectorDevTeam Alliance Registry"


default_alliance = {
    "family": None, # int guild id
    "guild": None,  # int guild id
    "name": "Default Name",  # str
    "tag": "ABCDE",  # str
    "leader" : None,
    "officers": None,  # int For the role id
    "members": None,  # int For the role id
    "bg1": None,
    "bg2": None,
    "bg3": None,
    "bg1aq": None,
    "bg1aw": None,
    "bg2aq": None,
    "bg2aw": None,
    "bg3aq": None,
    "bg3aw": None,
    "advanced_mode": False,
    "poster": None,  # str An image link, NOTE use aiohttp for this
    "summary": None,  # str The summary of the alliance
    "registered": False,
    "creation_date": None,
    "invite_url": None,
}

class AllianceData(MixinMeta, metaclass=CompositeMetaClass):
    """Alliance Data by CollectorDevTeam"""


    @mcocgroup.group(name="alliance")
    @CDT.is_supporter()
    @commands.guild_only()
    async def alliancegroup(self, ctx: Context):
        """MCOC Alliance commands"""
        pass

    async def find_user_alliance_ids(self, ctx, user: Optional[discord.User]):
        """Find user in  guild"""
        if user is None:
            user = ctx.author
        try:
            aidlist = await self.config.user(user.id).allianceids.all()
        except:
            await self.config.register_user(**self.default_user_profile)
            raise exceptions.MODOKError("ALLIANCE ID NOT FOUND!")    
        if len(aidlist) == 0: #if there are no ids in a user's alliance list
           async with self.config.alliance_registry.alliances() as alliances:
               for alliance in alliances.keys(): 
                    guild = await self.get_alliance_guild(ctx, alliance)
                    if guild is None:
                        raise exceptions.MODOKError("Uh oh captain, we lost a guild id.")
                    else:
                        if user in guild.members():     
                            members = CDT.list_role_members(self, ctx, guild, guild.get_role(alliance))
                            if user in members:
                                await self.config.user(user.id).allianceids.append(alliance)
        else:
            for aid in aidlist:
                async with self.config.alliance_registery.alliances(aid) as alliance:
                    guild = self.bot.get_guild(alliance["guild"])
                    if user in guild.members:
                        members = guild.get_role(alliance)
                        memberlist = CDT.list_role_members(self, ctx, guild, members)
                        if user in memberlist:
                            aidlist.append(alliance)
        if len(aidlist) == 0:
            return None
        return aidlist

    async def get_alliance_guild(self, ctx, alliance_id):
        """Helper function, retrieve discord.Guild object from alliance id"""
        if alliance_id in self.config.alliance_registry.alliances():
            gid = await self.config.alliance_registry.alliances["guild"]
            guild : discord.Guild = self.bot.get_guild(gid)
            return guild

        
    async def alliance_officer_check(self, ctx, alliance_id, user: Optional[discord.User]):
        """Check user in alliance Officers"""
        if user is None:
            user = ctx.author
        
        guild = self.bot.get_guild(self.config.alliance_registry.alliances(alliance_id).guild())
        if guild is None:
            ctx.send("No guild in registration. Big problem")
        else:
            oid = self.config.alliances(alliance_id).officers()
            officers = guild.get_role(oid)
            if officers is None:
                ctx.send("Alliance has no valid officers role. Big problem")
            else:
                if user in CDT.list_role_members(self, ctx, guild, officers):
                    return True
            leader = self.config.alliances(alliance_id).leader()




    @alliancegroup.command(name="create", aliases=("register",))
    @commands.guild_only()
    @commands.admin()
    async def alliance_create(self, ctx, alliance_role: Optional[discord.Role]):
        """Create a CollectorVerse alliance
        Args:
            ctx ([type]): [description]
            alliance_role (Optional[discord.Role]): A role designated for Alliance members must be specified and cannot be 'everyone'.

        """
        if alliance_role.id in await self.config.guild(ctx.guild).alliances():
            data = CDT.create_embed(title="Error! Alliance already registered", footer_text=ALLIANCE_FOOTER)
            await ctx.send(embed=data)
            return
        else:
            guild = ctx.guild
            new_alliance = default_alliance
            # new_alliance["alliance_id"].update(alliance_role.id)
            new_alliance["name"].update(guild.name)
            new_alliance["guild"].update(guild.id)
            question = '{0.mention}, do you want to register the role {1.mention} as a CollectorVerse Alliance?\n' \
                'Any member on your guild with this role will be considered a member of this alliance.\n'.format(ctx.author, alliance_role) 

            if len(alliance_role.members) > 30:
                question += ':warning:\nThe requested Alliance Role has more than 30 members.\n'

            question += 'If you have any of the following roles, they will be automatically bound. ```alliance, officers, bg1, bg2, bg3```\n' \

            for role in guild.roles:
                for k in ("officers", "bg1", "bg2", "bg3"):
                    if role.name.lower() == k:
                        new_alliance[k].update(role)
                        question += "{0} role found: {1.mention}\n".format(k, role)
        
            question +=':warning:\n' \
                'The Alliance tool will not function unless an **alliance** role is designated.\n' \
                'If you delete the role {0.mention}, you will effectively delete this alliance registration.\n' \
                'If you have other issues, use the command ``/mcoc alliance settings`` to view and verify your settings.\n'.format(alliance_role)

            answer = await CDT.confirm(ctx, question)
            if answer is True:
                await self._create_alliance(self, ctx, alliance_role, new_alliance)

    async def _create_alliance(self, ctx, guild, role, new_alliance):
        """Create alliance.
        Set basic information"""
        with self.config.guild(guild).alliances() as alliances:
            alliances.update({role.id: new_alliance})
        data = CDT.create_embed(title="CollectorVerse Alliance Registry", url=CDT.PATREON, footer_text=ALLIANCE_FOOTER)
        data.add_field(name="Congrats!:sparkles:",
                       value='{0.mention}, you have officially registered {1.name} as a CollectorVerse Alliance.\n'
                             ':warning: Protect the alliance role = {2.mention}! If this role is deleted then this alliance registration will be destroyed.\n'
                             'If you have other issues, use the command ``/mcoc alliance settings`` to view and verify your settings.\n'
                             'For additional support visit the CollectorDevTeam ``/joincdt``.\n'
                             'Reminder: Patrons receive priority support.\n'
                       .format(ctx.author, guild, role)) 

        await ctx.send(embed=data)
        return



    @alliancegroup.command(name="read")
    async def read_alliance(self, ctx, user: Optional[discord.User]):
        """Display alliance card"""
        if ctx.invoked_subcommand is None:
            if user is None:
                user = ctx.author
            await self._show_public(ctx, user)


## UPDATE GROUP
    # @alliancegroup.group(name="update", aliases=("set"))
    # @commands.guild_only()
    # async def alliance_update(self, ctx):
    #     """Update alliance settings"""
    #     aids = self.find_user_alliance_ids(ctx, ctx.message.author)
    #     if ctx.guild.id in aids and aids is not None:
    #         aid = ctx.guild.id
    #         async with self.config.alliances_registry.alliances(aid) as alliance:
    #             if alliance["officers"] is not None:
    #                 #//// check user permissions owner or managroles
    #                 officers = ctx.guild.get_role(alliance["officers"])
    #                 if officers in ctx.author.roles:
    #                     pass
    #             else:
    #                 pass

            


    # @alliance_update.command(name='officers')
    # @commands.admin_or_permissions(manage_roles=True)
    # async def _officers(self, ctx, role: discord.Role ):
    #     """Which role are your Alliance Officers?"""
    #     data = await self._update_role(ctx, key='officers', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg1')
    # async def _bg1(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 1?"""
    #     print("updating bg1")
    #     data = await self._update_role(ctx, key='bg1', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg1aq')
    # async def _bg1aq(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 1 for Alliance Quest?"""
    #     data = await self._update_role(ctx, key='bg1aq', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg1aw')
    # async def _bg1aw(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 1 for Alliance War?"""
    #     data = await self._update_role(ctx, key='bg1aw', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg2')
    # async def _bg2(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 2?"""
    #     data = await self._update_role(ctx, key='bg2', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg2aq')
    # async def _bg2aq(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 2 for Alliance Quest?"""
    #     data = await self._update_role(ctx, key='bg2aq', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg2aw')
    # async def _bg2aw(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 2 for Alliance War?"""
    #     data = await self._update_role(ctx, key='bg2aw', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg3')
    # async def _bg3(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 3?"""
    #     data = await self._update_role(ctx, key='bg3', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg3aq')
    # async def _bg3aq(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 3 for Alliance Quest?"""
    #     data = await self._update_role(ctx, key='bg3aq', role=role)
    #     await ctx.send(embed=data)

    # @alliance_update.command(name='bg3aw')
    # async def _bg3aw(self, ctx, role: discord.Role):
    #     """Which role is your Battlegroup 3 for Alliance War?"""
    #     data = await self._update_role(ctx, key='bg3aw', role=role)
    #     await ctx.send(embed=data)






    @alliancegroup.command(name="delete")
    async def alliance_delete(self, ctx):
        """Delete alliance registration"""


