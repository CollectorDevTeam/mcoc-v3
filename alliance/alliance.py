import aiohttp
import discord

from redbot.core import commands, Config
from redbot.core.bot import Red

from typing import Union, Optional

from datetime import datetime
from contextlib import suppress

from .abc import AllianceMeta
from .validator import *

import logging


_config_structure = {
    "guild": {
        "name": None, # str
        "officers": None, # int For the role id
        "members": None, # int For the role id
        "poster": None, # str An image link, NOTE use aiohttp for this
        "summary": None, # str The summary of the alliance
        "registered": False,
        "creation_date": None,
        "invite_url": None,
    },
    "user": {
        "alliance_guild": None, # int For the guild id
        "in_alliance": False,
    }
}


def officer_check():
    async def pred(ctx: commands.Context):
        if not await ctx.cog.config.guild(ctx.guild).registered():
            return False
        if ctx.guild.owner == ctx.author:
            return True
        officer_role = await ctx.cog.guild(ctx.guild).officers()
        if officer_role is None:
            return False
        return officer_role in [r.id for r in ctx.author.roles]
    return commands.check(pred)


class Alliance(Validator, commands.Cog, metaclass=AllianceMeta):
    """Keep track of your alliance"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 544974305445019651, True)
        self.config.register_guild(
            **_config_structure["guild"]
        )
        self.config.register_user(
            **_config_structure["user"]
        )
        self.session = aiohttp.ClientSession()
        with suppress(RuntimeError):
            self.bot.add_dev_env_value("alliance", lambda x: self)
        self.log = logging.getLogger("red.mcoc-v3.alliance")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        with suppress(KeyError):
            self.bot.remove_dev_env_value("alliance")

    @commands.group(invoke_without_command=True)
    async def alliance(self, ctx: commands.Context, user: Optional[discord.User]):
        """View a user's alliance!

        If no user is provided it will default to your alliance
        """
        user = user or ctx.author
        data = await self.config.user(user).all()
        if not data["in_alliance"]:
            return await ctx.send(f"{user.name} is not in an alliance")
        gid = data["alliance_guild"]
        try:
            guild_data = await self.config.guild_from_id(gid).all()
        except Exception as e:
            self.log.debug("Error in command alliance", exc_info=e)
            return await ctx.send("Something went'a wrong")
        guild = self.bot.get_guild(gid)
        name = guild_data["name"]
        summary = guild_data["summary"] or "No summary"
        poster = guild_data["poster"]
        creation = f"<t:{int(cd)}:d>" if (cd := guild_data["creation_date"]) else "No creation date given"
        invite = guild_data["invite_url"]
        if await ctx.embed_requested():
            embed = discord.Embed(
                title=name,
                description=summary,
                colour=discord.Colour.gold(),
                timestamp=datetime.utcnow(),
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
            embed.set_thumbnail(url=guild.icon_url)
            embed.set_footer(text="CDT Alliance System")
            embed.add_field(name="Founded on", value=creation)
            if poster:
                embed.set_image(url=poster)
            if invite:
                embed.add_field(name="Guild Invite", value=invite)
            kwargs = {"embed": embed}
        else:
            msg = f"**{name}**\n\n{summary}\n**Founded on**\n{creation}"
            if invite:
                msg += f"\n**Invite**\n{invite}"
            if poster:
                msg += f"\n\n{poster}"
            kwargs = {"content": poster}

        await ctx.send(**kwargs)

    @alliance.command(name="join")
    @commands.guild_only()
    async def alliance_join(self, ctx: commands.Context):
        """Join an alliance"""
        data = await self.config.user(ctx.author).all()
        guild_data = await self.config.guild(ctx.guild).all()
        if not guild_data.get("registered"):
            return await ctx.send("This guild has not registered as an alliance")

        maybe_role = guild_data.get("members")
        maybe_officer_role = guild_data.get("officers")

        if not maybe_role and not maybe_officer_role:
            return await ctx.send("This guild does not have a member role set up")

        officer_role = ctx.guild.get_role(maybe_officer_role)
        member_role = ctx.guild.get_role(maybe_role)

        if officer_role and officer_role in ctx.author.roles:
            status = "an Officer"
        elif member_role and member_role in ctx.author.roles:
            status = "a Member"
        else:
            return await ctx.send("You are not a part of this alliance! Ask a staff member to add a role to you")

        await ctx.send(f"You have joined {guild_data['name']} as {status}")
        await self.config.user(ctx.author).in_alliance.set(True)
        await self.config.user(ctx.author).alliance_guild.set(ctx.guild.id)

    @alliance.command(name="template")
    async def alliance_template(self, ctx: commands.Context):
        """Get the template for creating an alliance server"""
        use_embeds = await ctx.embed_requested()
        cdt_template = (
            "[CDT Alliance Template](https://discord.new/gtzuXHq2kCg4)"
            if use_embeds
            else "CDT Alliance Template (https://discord.new/gtzuXHq2kCg4)"
        )
        cdt_invite = (
            "[CollectoDevTeam Server](https://discord.com/BwhgZxk)"
            if use_embeds
            else "CollectorDevTeam Server (https://discord.com/BwhgZxk)"
        )
        msg = (
            f"1. Use the {cdt_template} to create a new server\n"
            f"2. Invite Collector using `{ctx.clean_prefix}invite`\n"
            f"3. Add announcements to #announcements with `{ctx.clean_prefix}announceset channel announcements`\n"
            f"4. Use `{ctx.clean_prefix}alliance create` to register your alliance with Collector.\n"
            f"5. Visit the {cdt_invite} to get support"
        )

        kwargs = {"content": f"**Alliance Server Creation Tool**\n\n{msg}\n<t:{int(datetime.now().timestamp())}>"}

        if await ctx.embed_requested():
            embed = discord.Embed(
                title="Alliance Server Creation Tool",
                description=msg,
                colour=discord.Colour.gold(),
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/icons/215271081517383682/a_d1fe1587f1981c8d2e0ebc353784f78a.gif?size=1024")
            embed.set_footer(text="Brought to you by the CollectorDevTeam™")
            kwargs = {"embed": embed}
        await ctx.send(**kwargs)

    @alliance.command(name="add", aliases=["create"])
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def alliance_add(self, ctx: commands.Context, *, name: str):
        """Set this guild as an alliance guild"""
        if await self.config.guild(ctx.guild).registered():
            return await ctx.send("This guild is already registered!")
        elif len(name) > 50:
            return await ctx.send("Alliance names cannot be longer than 50 characters")
        await self.config.guild(ctx.guild).registered.set(True)
        await self.config.guild(ctx.guild).name.set(name)
        await ctx.send(
            f"Your alliance is now registered with CDT. Use `{ctx.clean_prefix}alliance settings` to setup your alliance"
        )

    @commands.group(name="alliancesettings", aliases=["allianceset"])
    @commands.guild_only()
    @officer_check()
    async def alliance_settings(self, ctx: commands.Context):
        """Commands for setting up your alliance"""
        pass

    @alliance_settings.command(name="name")
    async def alliance_name(self, ctx: commands.Context, *, name: str):
        """Set the name of your alliance"""
        if not await self.config.guild(ctx.guild).registered():
            return await ctx.send(
                f"Your guild is not registered with CDT! Use `{ctx.clean_prefix}alliance add` to create one"
            )
        await self.config.guild(ctx.guild).name.set(name)
        await ctx.send(f"Your alliance's name is now `{name}`")

    @alliance_settings.command(name="members", aliases=["member"])
    async def alliance_members(self, ctx: commands.Context, role: discord.Role):
        """Set a role as the members role"""
        data = await self.config.guild(ctx.guild).all()
        old_role = data["members"]
        allowed_mentions = discord.AllowedMentions(roles=False)
        if not data["registered"]:
            return await ctx.send("This guild is not registered!")
        elif old_role is not None and ctx.guild.get_role(old_role) == role:
            return await ctx.send(
                f"The members role is already `{role.name}`"
            )
        await ctx.send(f"The members role is now `{role.name}`")
        await self.config.guild(ctx.guild).members.set(role.id)

    @alliance_settings.command(name="officers", aliases=["officer"])
    @commands.guildowner()
    async def alliance_officers(self, ctx: commands.Context, role: discord.Role):
        """Set a role as the officers role"""

        data = await self.config.guild(ctx.guild).all()
        old_role = data["officers"]
        if not data["registered"]:
            return await ctx.send("This guild is not registered!")
        elif old_role is not None and ctx.guild.get_role(old_role) == role:
            return await ctx.send(f"The officers role is already `{role.name}`")
        await ctx.send(f"The officers role is now `{role.name}`")
        await self.config.guild(ctx.guild).officers.set(role.id)

    @alliance_settings.command(name="founded")
    async def alliance_created_at(self, ctx: commands.Context, month: int, day: int, year: int):
        """Set the time your alliance was founded at"""
        if not await self.config.guild(ctx.guild).registered():
            return await ctx.send("This guild is not registered")
        try:
            date = datetime(year, month, day).timestamp() # grab the timestamp
        except ValueError:
            return await ctx.send("That was an invalid date!")
        await ctx.send(f"I have set the creation date of your alliance to <t:{int(date)}:d>")
        await self.config.guild(ctx.guild).creation_date.set(date)

    @alliance_settings.command(name="summary")
    async def alliance_summary(self, ctx: commands.Context, *, summary: str):
        """Set the summary of your alliance"""
        if not await self.config.guild(ctx.guild).registered():
            return await ctx.send("This guild is not registered")
        await self.config.guild(ctx.guild).summary.set(summary)
        await ctx.send("Done. That is now your summary")

    @alliance_settings.command(name="poster")
    async def alliance_poster(self, ctx: commands.Context, url: str):
        """Set the poster for your alliance"""
        if not await self.config.guild(ctx.guild).registered():
            return await ctx.send("This guild is not registered")
        try:
            url = await self._validate_url(url)
        except BadImage as e:
            return await ctx.send(e.args[0])
        else:
            if not url:
                return await ctx.send("That url was not valid!")
        await ctx.send("Done. Set that as your poster")
        await self.config.guild(ctx.guild).poster.set(url)

    @alliance_settings.command(name="invite")
    async def alliance_invite(self, ctx: commands.Context, invite: discord.Invite):
        """Set an invite url for your alliance"""
        if not await self.config.guild(ctx.guild).registered():
            return await ctx.send("This guild is not registered")
        await ctx.send(f"Done. {discord.utils.escape_markdown(invite.url)} has been set as your invite url")
        await self.config.guild(ctx.guild).invite_url.set(invite.url)
