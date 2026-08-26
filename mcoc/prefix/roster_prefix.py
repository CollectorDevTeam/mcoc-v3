# mcoc/prefix/roster_prefix.py
import logging
from typing import Optional, Any, List, Dict
from redbot.core import commands

import discord
from mcoc.common.champion_helpers import add_page_footers
from mcoc.common.componentsV2 import CDTv2, PaginatorView

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
    async def roster(self, ctx, *items: str):
        """
        Top-level roster group.
        Behavior:
          - no args -> show help text
          - args present -> treat as `roster list <args>` (so `///mcoc roster @user` becomes list)
        """
        # If no args, show help
        if not items:
            await ctx.send(ROSTER_GROUP_HELP.get("roster", "Roster commands: add, remove, update, list, export, clear"))
            return

        # If args present, forward to the list handler so `///mcoc roster @user ...` works
        try:
            await self.roster_list(ctx, *items)
        except Exception:
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
        Usage:
        ///mcoc roster list                -> your roster
        ///mcoc roster list @user           -> other user's roster (if allowed)
        ///mcoc roster list @user 6*r4      -> other user's roster filtered
        """
        if not await self._require_parent(ctx):
            return

        # If first token looks like a user mention/id, resolve it and treat as target
        target_member = None
        items_list = list(items or [])
        if items_list:
            first = items_list[0]
            try:
                # Use MemberConverter in guild, otherwise UserConverter
                if ctx.guild:
                    target_user = await commands.MemberConverter().convert(ctx, first)
                else:
                    target_user = await commands.UserConverter().convert(ctx, first)
                # conversion succeeded -> prefer guild Member if available
                if ctx.guild and isinstance(target_user, discord.Member):
                    target_member = target_user
                else:
                    target_member = target_user
                # remove the resolved token from filters
                items_list = items_list[1:]
            except Exception:
                # conversion failed -> leave items_list intact and do not set target_member
                target_member = None

        if target_member is None:
            target_member = ctx.author


        items_text = " ".join(items_list).strip()
        parsed = parse_hargs(items_text) if items_text else {}

        # privacy check: if target is not the invoking user, check profile privacy
        users = ensure_user_manager(self.parent)
        profile = users.get_profile(target_member.id) if users and hasattr(users, "get_profile") else {}
        # Example privacy flag: profile.get("public_roster", True)
        if target_member.id != ctx.author.id:
            if profile.get("public_roster") is False:
                await ctx.send("That user's roster is private.")
                return

        # Build pages (pass target_member for branding so avatar shows)
        pages = await build_roster_pages(self.parent, target_member, parsed)

        if not pages:
            await ctx.send(embed=CDTv2.embed(target_member, title="Roster", description="No roster entries match your filters."))
            return

        # Optional: add page footers (mutates pages) before creating pager
        try:
            pages = add_page_footers(pages, author_for_embed=target_member)
        except Exception:
            try:
                pages = add_page_footers(pages, author_for_embed=ctx.author)
            except Exception:
                pass

        # Ensure pages are embeds (CDTv2.embed will have been used by build_roster_pages)
        try:
            pager = PaginatorView(pages, author=ctx.author)
            await pager.start(ctx)

            # Merge brand buttons into the pager view (preferred)
            try:
                brand_view = CDTv2.brand_view()
                for item in getattr(brand_view, "children", []):
                    pager.add_item(item)
                if pager.message:
                    await pager.message.edit(view=pager)
            except Exception:
                # fallback: send brand buttons as separate message
                try:
                    view = CDTv2.brand_view()
                    await ctx.send(view=view)
                except Exception:
                    pass

        except Exception:
            names = [getattr(p, "title", "Entry") for p in pages][:50]
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
    async def roster_import(self, ctx, *, data: str = None):
        """
        Import roster from JSON text or from an attached file.
        Usage:
        ///mcoc roster import {"champions":[...]}
        ///mcoc roster import   (with a .json attachment)
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        cache = getattr(self.parent, "cache", None)

        raw = data
        # If no inline data, try to read first attachment
        if not raw:
            try:
                msg = getattr(ctx, "message", None)
                if msg and getattr(msg, "attachments", None):
                    att = msg.attachments[0]
                    # prefer reading bytes/text (discord.py Attachment has .read())
                    try:
                        raw_bytes = await att.read()
                        raw = raw_bytes.decode("utf-8", errors="ignore")
                    except Exception:
                        # fallback to URL fetch (less ideal) or skip
                        raw = None
            except Exception:
                raw = None

        if not raw:
            await ctx.send("No import data provided. Attach a JSON file or pass JSON text inline.")
            return

        # Try JSON parse first
        import json
        parsed_list = None
        try:
            j = json.loads(raw)
            # Accept either top-level list or {"champions": [...]}
            if isinstance(j, list):
                parsed_list = j
            elif isinstance(j, dict) and isinstance(j.get("champions"), list):
                parsed_list = j.get("champions")
            else:
                # maybe it's a dict mapping slug->entry; normalize to list
                if isinstance(j, dict):
                    parsed_list = []
                    for k, v in j.items():
                        if isinstance(v, dict):
                            v.setdefault("champion", k)
                            parsed_list.append(v)
        except Exception:
            parsed_list = None

        # If JSON parse failed, try to treat raw as hargs text and parse tokens
        if parsed_list is None:
            try:
                # parse_roster_entries_from_input will resolve names to slugs if cache available
                parsed_list = parse_roster_entries_from_input(raw, cache)
            except Exception:
                parsed_list = None

        if not parsed_list:
            await ctx.send("Failed to parse import data. Provide valid JSON or a roster hargs text file.")
            return

        successes = []
        failures = []
        for item in parsed_list:
            try:
                # Normalize expected fields
                champ_slug = item.get("champion") or item.get("slug") or item.get("name")
                rarity = int(item.get("rarity") or item.get("stars") or 6)
                rank = int(item.get("rank") or 1)
                sig = int(item.get("sig") or 0)
                asc = int(item.get("ascended") if "ascended" in item else item.get("asc", 1))

                # If champion is a name, try to resolve via cache
                if cache and champ_slug and not isinstance(champ_slug, str):
                    champ_slug = str(champ_slug)

                # If champ_slug looks like a name, try to resolve to slug
                try:
                    if cache:
                        # cache.get_champion accepts slug or id; if name provided, try resolve
                        cobj = cache.get_champion(champ_slug)
                        if not cobj:
                            # try name scan
                            for c in getattr(cache, "get_all_champions", lambda: [])() or []:
                                if (c.get("name") or "").lower() == str(champ_slug).lower():
                                    cobj = c
                                    break
                        if cobj:
                            champ_slug = cobj.get("id") or cobj.get("slug")
                except Exception:
                    pass

                # Use update_champion (or add_champion depending on desired semantics)
                updated = users.update_champion(
                    ctx.author.id,
                    champ_slug=champ_slug,
                    rarity=rarity,
                    rank=rank,
                    sig=sig,
                    ascended=asc,
                )
                if updated:
                    successes.append(f"{champ_slug}: updated")
                else:
                    # fallback to add if update didn't find an existing entry
                    try:
                        users.add_champion(ctx.author.id, champ_slug=champ_slug, rarity=rarity, rank=rank, sig=sig, ascended=asc)
                        successes.append(f"{champ_slug}: added")
                    except Exception:
                        failures.append(f"{champ_slug}: failed to add/update")
            except Exception:
                failures.append(f"{item.get('champion') or str(item)}: error")

        # schedule persist
        try:
            schedule_persist_user_prestige(self.parent, ctx.author.id)
        except Exception:
            pass

        lines = []
        if successes:
            lines.append("Imported/Updated:")
            lines.extend(f"- {s}" for s in successes)
        if failures:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {f}" for f in failures)
        await ctx.send("\n".join(lines))

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

    @_safe_add("roster")
    async def _roster(ctx, *items: str):
        """Top-level roster group for dynamic registration."""
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return

        if not items:
            await ctx.send(ROSTER_GROUP_HELP.get("roster", "Roster commands: add, remove, update, list, export, clear"))
            return

        # Forward to the registered list command (the dynamic _list implementation)
        try:
            # The dynamic _list function is registered under the same group; call it directly
            await _list(ctx, *items)
        except Exception:
            await ctx.send(ROSTER_GROUP_HELP.get("roster", "Roster commands: add, remove, update, list, export, clear"))


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

        # Resolve optional leading user mention/id (same logic as class-based roster_list)
        target_member = None
        items_list = list(items or [])
        if items_list:
            first = items_list[0]
            try:
                if ctx.guild:
                    target_user = await commands.MemberConverter().convert(ctx, first)
                else:
                    target_user = await commands.UserConverter().convert(ctx, first)
                if ctx.guild and isinstance(target_user, discord.Member):
                    target_member = target_user
                else:
                    target_member = target_user
                items_list = items_list[1:]
            except Exception:
                target_member = None

        if target_member is None:
            target_member = ctx.author

        items_text = " ".join(items_list).strip()
        parsed = parse_hargs(items_text) if items_text else {}

        # privacy check: if target is not the invoking user, check profile privacy
        users = ensure_user_manager(parent)
        profile = users.get_profile(target_member.id) if users and hasattr(users, "get_profile") else {}
        if target_member.id != ctx.author.id:
            if profile.get("public_roster") is False:
                await ctx.send("That user's roster is private.")
                return

        # Build pages (pass target_member for branding/avatar)
        pages = await build_roster_pages(parent, target_member, parsed)

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
        """Clear your roster."""
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; roster unavailable.")
            return
        users = ensure_user_manager(parent)
        if users:
            users.delete_user(ctx.author.id)
        await ctx.send("Your roster has been cleared.")
