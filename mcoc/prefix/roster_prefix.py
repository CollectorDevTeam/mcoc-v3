# mcoc/prefix/roster_prefix.py
import logging
from typing import Optional, Any, List, Dict
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.roster")

from ..common.hargs import parse_hargs
from ..common.roster_helpers import (
    ensure_user_manager,
    extract_entry_from_parsed,
    build_roster_pages,
    validate_entry_for_add,
    schedule_persist_user_prestige,
    # use the new adapter that resolves slugs via cache
    parse_roster_entries_from_input,
)
from ..common.embeds import roster_entry_embed  # used for embed building
from ..common.prefix_utils import get_runtime_prefix

from ..common.prefix_meta import ROSTER_GROUP_HELP, ALLOWED_ROSTER_FIELDS


class RosterPrefix(commands.Cog):
    """
    Prefix commands for roster management. Uses common roster helpers.

    Add/Remove/Update accept lists of ChampionHargs / HargsChampion / plain champion tokens.
    Example inputs:
      ///mcoc roster add blackbolt6sr1, spiderman6r1
      ///mcoc roster add "Black Bolt" 6r1; "Spider Man" 6r1
      ///mcoc roster add 6r1blackbolt 6A1r2spiderman
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
        await ctx.send(ROSTER_GROUP_HELP.get("roster", "Roster commands: add, remove, update, list, export, clear"))

    # -----------------------------
    # Add (multiple)
    # -----------------------------
    @roster.command(name="add")
    async def roster_add(self, ctx, *items: str):
        """
        Add one or more champions to your roster.
        Accepts lists of ChampionHargs / HargsChampion / plain champion tokens.
        Examples:
          ///mcoc roster add blackbolt6sr1, spiderman6r1
          ///mcoc roster add "Black Bolt" 6r1; "Spider Man" 6r1
        """
        prefix = get_runtime_prefix(ctx, default="///")
        if not items:
            await ctx.send(
                "Usage: "
                f"`{prefix}mcoc roster add <championHargs|hargsChampion|\"Champion Name\">[, ...]`"
            )
            return

        if not await self._require_parent(ctx):
            return

        items_text = " ".join(items).strip()
        cache = getattr(self.parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception as exc:
            log.exception("Unexpected error parsing roster add input: %s", exc)
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(self.parent)

        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion")
                # try to resolve champion via cache
                champ_obj = None
                if cache and champ_key:
                    try:
                        champ_obj = cache.get_champion(champ_key)
                    except Exception:
                        champ_obj = None
                if not champ_obj and cache and champ_key:
                    # try name scan
                    try:
                        for c in getattr(cache, "get_all_champions", lambda: [])() or []:
                            if str(c.get("id") or c.get("slug") or "").lower() == str(champ_key).lower() or str(c.get("name") or "").lower() == str(champ_key).lower():
                                champ_obj = c
                                break
                    except Exception:
                        champ_obj = None

                if not champ_obj:
                    failures.append(f"{champ_key or entry.get('raw')}: champion not found")
                    continue

                # validate entry
                if not validate_entry_for_add(entry):
                    failures.append(f"{champ_obj.get('name','Unknown')}: invalid hargs (rarity/rank/ascension/sig)")
                    continue

                users.add_champion(
                    ctx.author.id,
                    champ_slug=champ_obj.get("id") or champ_obj.get("slug"),
                    rarity=entry["rarity"],
                    rank=entry["rank"],
                    sig=entry.get("sig", 0),
                    tags=entry.get("tags", []),
                    ascended=entry.get("ascended", 0) if "ascended" in entry else entry.get("ascended", 1),
                )
                successes.append(f"{champ_obj.get('name','Unknown')} ({entry['rarity']}★ r{entry['rank']} s{entry.get('sig',0)} A{entry.get('ascended',1)})")
            except Exception:
                log.exception("Failed to add entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        # schedule one debounced persist
        try:
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after add")

        # Build response
        lines = []
        if successes:
            lines.append("Added:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # -----------------------------
    # Remove (multiple)
    # -----------------------------
    @roster.command(name="remove")
    async def roster_remove(self, ctx, *items: str):
        """
        Remove one or more champions from your roster.
        Input may be champion name or hargs to disambiguate.
        Examples:
          ///mcoc roster remove blackbolt, spiderman
          ///mcoc roster remove 6r1blackbolt, 6r1spiderman
        """
        if not items:
            await ctx.send("Usage: `///mcoc roster remove <champion|hargs>[, ...]`")
            return
        if not await self._require_parent(ctx):
            return

        items_text = " ".join(items).strip()
        cache = getattr(self.parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception as exc:
            log.exception("Unexpected error parsing roster remove input: %s", exc)
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(self.parent)
        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion") or entry.get("raw")
                # If rarity provided, pass it to remove_champion to narrow removal
                rarity = entry.get("rarity")
                removed = users.remove_champion(ctx.author.id, champ_key, rarity)
                if removed:
                    successes.append(f"{champ_key}: removed {removed}")
                else:
                    failures.append(f"{champ_key}: not found")
            except Exception:
                log.exception("Failed to remove entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        # schedule one debounced persist
        try:
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after remove")

        lines = []
        if successes:
            lines.append("Removed:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # -----------------------------
    # Update (multiple)
    # -----------------------------
    @roster.command(name="update")
    async def roster_update(self, ctx, *items: str):
        """
        Update one or more champions in your roster.
        Each token should include rarity (or use defaults).
        Examples:
          ///mcoc roster update blackbolt6r3, spiderman6r2
        """
        if not items:
            await ctx.send("Usage: `///mcoc roster update <championHargs|hargsChampion|\"Champion Name\">[, ...]`")
            return
        if not await self._require_parent(ctx):
            return

        items_text = " ".join(items).strip()
        cache = getattr(self.parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception as exc:
            log.exception("Unexpected error parsing roster update input: %s", exc)
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(self.parent)
        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion") or entry.get("raw")
                if entry.get("rarity") is None:
                    failures.append(f"{champ_key}: missing rarity for update")
                    continue

                updated = users.update_champion(
                    ctx.author.id,
                    champ_slug=champ_key,
                    rarity=entry.get("rarity"),
                    rank=entry.get("rank"),
                    sig=entry.get("sig"),
                    tags=entry.get("tags"),
                    ascended=entry.get("ascended", 1),
                )
                if updated:
                    successes.append(f"{champ_key}: updated to {entry.get('rarity')}★ r{entry.get('rank',1)} s{entry.get('sig',0)} A{entry.get('ascended',1)}")
                else:
                    failures.append(f"{champ_key}: not found")
            except Exception:
                log.exception("Failed to update entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        # schedule one debounced persist
        try:
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after update")

        lines = []
        if successes:
            lines.append("Updated:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # -----------------------------
    # List (filters)
    # -----------------------------
    @roster.command(name="list")
    async def roster_list(self, ctx, *items: str):
        """
        List roster entries. Accepts the same filter syntax as parse_hargs.
        Examples:
          ///mcoc roster list
          ///mcoc roster list 6*r4, #attack
        """
        if not await self._require_parent(ctx):
            return

        items_text = " ".join(items).strip()
        parsed = parse_hargs(items_text) if items_text else {}
        pages = await build_roster_pages(self.parent, ctx.author.id, parsed)

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

    # -----------------------------
    # Export / Import / Clear (unchanged)
    # -----------------------------
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
    async def _add(ctx, *items: str):
        """Add one or more champions to your roster.
        Examples:
            {prefix}mcoc roster add 5sr3ironman
            {prefix}mcoc roster add 6★r2Spider-Man 4sr1s20captainamerica
            {prefix}mcoc roster add 3sr1blackwidow
        """
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        items_text = " ".join(items).strip()
        cache = getattr(parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception:
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(parent)

        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion")
                champ_obj = None
                if cache and champ_key:
                    try:
                        champ_obj = cache.get_champion(champ_key)
                    except Exception:
                        champ_obj = None
                if not champ_obj and cache and champ_key:
                    try:
                        for c in getattr(cache, "get_all_champions", lambda: [])() or []:
                            if str(c.get("id") or c.get("slug") or "").lower() == str(champ_key).lower() or str(c.get("name") or "").lower() == str(champ_key).lower():
                                champ_obj = c
                                break
                    except Exception:
                        champ_obj = None

                if not champ_obj:
                    failures.append(f"{champ_key or entry.get('raw')}: champion not found")
                    continue

                if not validate_entry_for_add(entry):
                    failures.append(f"{champ_obj.get('name','Unknown')}: invalid hargs")
                    continue

                users.add_champion(
                    ctx.author.id,
                    champ_slug=champ_obj.get("id") or champ_obj.get("slug"),
                    rarity=entry["rarity"],
                    rank=entry["rank"],
                    sig=entry.get("sig", 0),
                    tags=entry.get("tags", []),
                    ascended=entry.get("ascended", 1),
                )
                successes.append(f"{champ_obj.get('name','Unknown')} ({entry['rarity']}★ r{entry['rank']})")
            except Exception:
                log.exception("Failed to add entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        try:
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after add")

        lines = []
        if successes:
            lines.append("Added:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # remove
    @_safe_add("remove")
    async def _remove(ctx, *items: str):
        """Remove one or more champions from your roster.
        Examples:
            {prefix}mcoc roster remove 5sr3ironman
            {prefix}mcoc roster remove 6★r2Spider-Man 4sr1s20captainamerica
            {prefix}mcoc roster remove 3sr1blackwidow
        """
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        items_text = " ".join(items).strip()
        cache = getattr(parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception:
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(parent)
        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion") or entry.get("raw")
                rarity = entry.get("rarity")
                removed = users.remove_champion(ctx.author.id, champ_key, rarity)
                if removed:
                    successes.append(f"{champ_key}: removed {removed}")
                else:
                    failures.append(f"{champ_key}: not found")
            except Exception:
                log.exception("Failed to remove entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        try:
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after remove")

        lines = []
        if successes:
            lines.append("Removed:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # update
    @_safe_add("update")
    async def _update(ctx, *items: str):
        """Update one or more champions in your roster.
        Examples:
            {prefix}mcoc roster update 5sr3ironman
            {prefix}mcoc roster update 6★r2Spider-Man 4sr1s20captainamerica
            {prefix}mcoc roster update 3sr1blackwidow
        """
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        items_text = " ".join(items).strip()
        cache = getattr(parent, "cache", None)
        try:
            parsed_entries = parse_roster_entries_from_input(items_text, cache)
        except ValueError as exc:
            await ctx.send(f"No valid entries parsed from input: {exc}")
            return
        except Exception:
            await ctx.send("Error parsing entries; see logs for details.")
            return

        if not parsed_entries:
            await ctx.send("No valid entries parsed from input.")
            return

        users = ensure_user_manager(parent)
        successes: List[str] = []
        failures: List[str] = []

        for entry in parsed_entries:
            try:
                champ_key = entry.get("champion") or entry.get("raw")
                if entry.get("rarity") is None:
                    failures.append(f"{champ_key}: missing rarity for update")
                    continue

                updated = users.update_champion(
                    ctx.author.id,
                    champ_slug=champ_key,
                    rarity=entry.get("rarity"),
                    rank=entry.get("rank"),
                    sig=entry.get("sig"),
                    tags=entry.get("tags"),
                    ascended=entry.get("ascended", 1),
                )
                if updated:
                    successes.append(f"{champ_key}: updated")
                else:
                    failures.append(f"{champ_key}: not found")
            except Exception:
                log.exception("Failed to update entry %s", entry)
                failures.append(f"{entry.get('champion') or entry.get('raw')}: error")

        try:
            schedule_persist_user_prestige(parent, ctx.author.id)
        except Exception:
            log.exception("Failed to schedule prestige persist after update")

        lines = []
        if successes:
            lines.append("Updated:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

    # list
    @_safe_add("list")
    async def _list(ctx, *items: str):
        """List champions in your roster.
        Examples:
            {prefix}mcoc roster list
            {prefix}mcoc roster list #bleed
            {prefix}mcoc roster list 6star #bleed
        """
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        items_text = " ".join(items).strip()
        parsed = parse_hargs(items_text) if items_text else {}
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
        """Export your roster data as JSON.
        Examples:
            {prefix}mcoc roster export
        """
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
        """Clear your roster.
        Examples:
            {prefix}mcoc roster clear
        """
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        users = ensure_user_manager(parent)
        if users:
            users.delete_user(ctx.author.id)
        await ctx.send("Your roster has been cleared.")
