# mcoc/prefix/roster_prefix.py
import logging
from typing import Optional, Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.roster")

from ..common.hargs import parse_hargs
from ..common.roster_helpers import (
    ensure_user_manager,
    extract_entry_from_parsed,
    build_roster_pages,
    validate_entry_for_add,
    schedule_persist_user_prestige,
)
from ..common.embeds import roster_entry_embed  # used for embed building
from ..common.prefix_utils import get_runtime_prefix

from ..common.prefix_meta import ROSTER_GROUP_HELP, ALLOWED_ROSTER_FIELDS


class RosterPrefix(commands.Cog):
    """
    Prefix commands for roster management. Uses common roster helpers.
    """

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        # Try to attach core dynamically if possible
        if not getattr(self, "parent", None):
            try:
                core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
                if core:
                    self.parent = core
                    return True
            except Exception:
                pass
            try:
                await ctx.send("MCOC core not attached; roster unavailable.")
            except Exception:
                pass
            return False
        return True

    @commands.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx):
        # await ctx.send("Roster commands: add, remove, update, list, export, clear")
        await ctx.send(ROSTER_GROUP_HELP.get("roster", "Roster commands: add, remove, update, list, export, clear"))

    @roster.command(name="add")
    async def roster_add(self, ctx, champion: str, *, hargs: str):
        """Add a champion to your roster."""
        prefix = get_runtime_prefix(ctx, default=self.prefix or "///")
        lines = [ROSTER_GROUP_HELP.get("roster_add", "Add a champion to your roster.")]
        lines.append("")
        lines.append(f"Use `{prefix}mcoc roster add <champion> <hargs>` to add a champion to your roster.")
        await ctx.send("\n".join(lines))

        if not await self._require_parent(ctx):
            return
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        cache = getattr(self.parent, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        if not validate_entry_for_add(entry):
            await ctx.send("Adding a champion requires rarity and rank (e.g., `6*r3`).")
            return

        users = ensure_user_manager(self.parent)
        try:
            users.add_champion(
                ctx.author.id,
                champ_slug=champ.get("id") or champ.get("slug"),
                rarity=entry["rarity"],
                rank=entry["rank"],
                sig=entry.get("sig", 0),
                tags=entry.get("tags", []),
            )
            # schedule debounced prestige persistence
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to add champion to roster")
            await ctx.send("Failed to add champion to roster.")
            return

        try:
            embed = await roster_entry_embed(ctx, champ, {
                "rarity": entry["rarity"],
                "rank": entry["rank"],
                "sig": entry.get("sig", 0),
                "tags": entry.get("tags", []),
                "ascended": entry.get("ascended", 0),
            })
        except Exception:
            embed = None

        await ctx.send(f"Added **{champ.get('name','Unknown')}** to your roster.", embed=embed)

    @roster.command(name="remove")
    async def roster_remove(self, ctx, champion: str, *, hargs: Optional[str] = None):
        if not await self._require_parent(ctx):
            return
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        users = ensure_user_manager(self.parent)
        try:
            removed = users.remove_champion(ctx.author.id, champion, rarity)
        # schedule debounced prestige persistence
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to remove champion")
            removed = 0

        if removed == 0:
            await ctx.send("No matching champion found in your roster.")
        else:
            await ctx.send(f"Removed {removed} entries for `{champion}`.")

    @roster.command(name="update")
    async def roster_update(self, ctx, champion: str, *, hargs: str):
        if not await self._require_parent(ctx):
            return
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        if entry.get("rarity") is None:
            await ctx.send("Updating a champion requires rarity (e.g., `6*`).")
            return

        users = ensure_user_manager(self.parent)
        try:
            updated = users.update_champion(
                ctx.author.id,
                champ_slug=champion,
                rarity=entry["rarity"],
                rank=entry.get("rank"),
                sig=entry.get("sig"),
                tags=entry.get("tags"),
            )
            # schedule debounced prestige persistence
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to update champion")
            updated = False

        if not updated:
            await ctx.send("Champion not found in your roster.")
            return

        cache = getattr(self.parent, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        try:
            embed = await roster_entry_embed(ctx, champ, {
                "rarity": entry["rarity"],
                "rank": entry.get("rank") or 0,
                "sig": entry.get("sig") or 0,
                "tags": entry.get("tags") or [],
                "ascended": entry.get("ascended") or 0
            })
        except Exception:
            embed = None

        await ctx.send(f"Updated **{champ.get('name','Unknown') if champ else champion}**.", embed=embed)

    @roster.command(name="list")
    async def roster_list(self, ctx, *, hargs: Optional[str] = None):
        if not await self._require_parent(ctx):
            return
        parsed = parse_hargs(hargs or "")
        pages = await build_roster_pages(self.parent, ctx.author.id, parsed)

        if not pages:
            await ctx.send("No roster entries match your filters.")
            return

        try:
            from ..common.pagination import PagesMenu
            # try to add page footers if helper exists
            menu = PagesMenu(pages, ctx.author)
            try:
                from ..common.roster_helpers import add_page_footers  # optional
                pages = add_page_footers(pages)
            except Exception:
                pass
            # await ctx.send(embed=pages[0], view=menu)
            await menu.start(ctx)
        except Exception:
            names = [p.get("title") or "Entry" for p in pages][:50]
            await ctx.send(f"Matches ({len(pages)}): {', '.join(names)}")

    @roster.command(name="export")
    async def roster_export(self, ctx):
        users = ensure_user_manager(self.parent)
        data = users.export(ctx.author.id) if users else {}
        await ctx.send(f"Your roster data:\n```json\n{data}\n```")

    @roster.command(name="import")
    async def roster_import(self, ctx, *, data: str):
        users = ensure_user_manager(self.parent)
        if users:
            try:
                users.import_data(ctx.author.id, data)
                await ctx.send("Imported your roster data.")
            except Exception:
                await ctx.send("Failed to import roster data.")

    @roster.command(name="clear")
    async def roster_clear(self, ctx):
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        if users:
            users.delete_user(ctx.author.id)
        await ctx.send("Your roster has been cleared.")


def register_with_group(group: commands.Group, parent_getter):
    """
    Attach roster prefix commands to the provided `group`.
    parent_getter is a callable returning the core/parent object (or None).
    """

    def _safe_add(cmd_name):
        def _decorator(func):
            try:
                if group.get_command(cmd_name):
                    log.debug("Command %s already exists; skipping", cmd_name)
                    return func
            except Exception:
                pass
            group.command(name=cmd_name)(func)
            return func
        return _decorator

    # add
    @_safe_add("add")
    async def _add(ctx, champion: str, *, hargs: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        cache = getattr(parent, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        if not validate_entry_for_add(entry):
            await ctx.send("Adding a champion requires rarity and rank (e.g., `6*r3`).")
            return

        users = ensure_user_manager(parent)
        try:
            users.add_champion(
                ctx.author.id,
                champ_slug=champ.get("id") or champ.get("slug"),
                rarity=entry["rarity"],
                rank=entry["rank"],
                sig=entry.get("sig", 0),
                tags=entry.get("tags", []),
            )
            # schedule debounced prestige persistence
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to add champion to roster")
            await ctx.send("Failed to add champion to roster.")
            return

        try:
            embed = await roster_entry_embed(ctx, champ, {
                "rarity": entry["rarity"],
                "rank": entry["rank"],
                "sig": entry.get("sig", 0),
                "tags": entry.get("tags", []),
                "ascended": entry.get("ascended", 0),
            })
        except Exception:
            embed = None

        await ctx.send(f"Added **{champ.get('name','Unknown')}** to your roster.", embed=embed)

    # remove
    @_safe_add("remove")
    async def _remove(ctx, champion: str, *, hargs: Optional[str] = None):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        users = ensure_user_manager(parent)
        try:
            removed = users.remove_champion(ctx.author.id, champion, rarity)
            # schedule debounced prestige persistence
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to remove champion")
            removed = 0

        if removed == 0:
            await ctx.send("No matching champion found in your roster.")
        else:
            await ctx.send(f"Removed {removed} entries for `{champion}`.")

    # update
    @_safe_add("update")
    async def _update(ctx, champion: str, *, hargs: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        if entry.get("rarity") is None:
            await ctx.send("Updating a champion requires rarity (e.g., `6*`).")
            return

        users = ensure_user_manager(parent)
        try:
            updated = users.update_champion(
                ctx.author.id,
                champ_slug=champion,
                rarity=entry["rarity"],
                rank=entry.get("rank"),
                sig=entry.get("sig"),
                tags=entry.get("tags"),
            )
            # schedule debounced prestige persistence
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to update champion")
            updated = False

        if not updated:
            await ctx.send("Champion not found in your roster.")
            return

        cache = getattr(parent, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        try:
            embed = await roster_entry_embed(ctx, champ, {
                "rarity": entry["rarity"],
                "rank": entry.get("rank") or 0,
                "sig": entry.get("sig") or 0,
                "tags": entry.get("tags") or [],
                "ascended": entry.get("ascended") or 0
            })
        except Exception:
            embed = None

        await ctx.send(f"Updated **{champ.get('name','Unknown') if champ else champion}**.", embed=embed)

    # list
    @_safe_add("list")
    async def _list(ctx, *, hargs: Optional[str] = None):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        parsed = parse_hargs(hargs or "")
        pages = await build_roster_pages(parent, ctx.author.id, parsed)

        if not pages:
            await ctx.send("No roster entries match your filters.")
            return

        try:
            from ..common.pagination import PagesMenu
            menu = PagesMenu(pages, ctx.author)
            try:
                from ..common.roster_helpers import add_page_footers  # optional
                pages = add_page_footers(pages)
            except Exception:
                pass
            await menu.start(ctx)
        except Exception:
            names = [p.get("title") or "Entry" for p in pages][:50]
            await ctx.send(f"Matches ({len(pages)}): {', '.join(names)}")

    # export
    @_safe_add("export")
    async def _export(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        users = ensure_user_manager(parent)
        data = users.export(ctx.author.id) if users else {}
        await ctx.send(f"Your roster data:\n```json\n{data}\n```")

    # clear
    @_safe_add("clear")
    async def _clear(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        users = ensure_user_manager(parent)
        if users:
            users.delete_user(ctx.author.id)
        await ctx.send("Your roster has been cleared.")
