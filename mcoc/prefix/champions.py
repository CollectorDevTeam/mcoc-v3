# Path: mcoc/prefix/champions.py
# File-Version: 1.0
# Purpose: Champion prefix command surface.
# Public-API: ChampionsPrefix

from typing import Any, Optional
import logging

from redbot.core import commands

from mcoc.common import Core
from mcoc.common.utilities.query_parser import parse_query
from mcoc.common.components.prefix_utils import safe_send_ctx

Embed = Core.Embed
PagesMenu = Core.PagesMenu
Champions = Core.Helpers.champions
Entitlements = Core.Entitlements

log = logging.getLogger("red.mcoc.prefix.champions")


def _normalize_lookup_token(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower().strip().replace("_", "-")
    text = text.replace("&", " and ")
    return "".join(ch for ch in text if ch.isalnum())


class ChampionsPrefix(commands.Cog):
    """Prefix commands for champion search and utilities."""

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; champion commands unavailable.")
            return False
        return True

    def _champion_admin_guard(self, ctx) -> bool:
        """Allow only CollectorDevTeam role members or champion-admin entitlements."""
        if not getattr(ctx, "guild", None):
            return False
        roles = getattr(ctx.author, "roles", [])
        if any(getattr(role, "name", "").lower() == "collectordevteam" for role in roles):
            return True
        if getattr(ctx.author, "id", None) == getattr(ctx.guild, "owner_id", None):
            return True
        try:
            guild_cfg = getattr(getattr(self.parent, "feature_cfg", None), "guild_cfg", None)
            if guild_cfg is not None:
                return bool(Entitlements.has_feature(ctx, guild_cfg, "champion_admin"))
        except Exception:
            pass
        return False

    def _resolve_champion_record(self, cache: Any, name_or_alias: str) -> Optional[dict]:
        if not cache or not name_or_alias:
            return None
        try:
            champ = cache.get_champion(name_or_alias)
            if champ:
                return champ
        except Exception:
            pass

        needle = _normalize_lookup_token(name_or_alias)
        for champ in (cache.get_all_champions() or []):
            if not isinstance(champ, dict):
                continue
            choices = [
                champ.get("id"),
                champ.get("slug"),
                champ.get("name"),
                champ.get("title"),
                champ.get("shortname"),
                *(champ.get("aliases") or []),
            ]
            for choice in choices:
                if choice is None:
                    continue
                if _normalize_lookup_token(choice) == needle:
                    return champ
        return None

    def _save_champion_metadata(self, target: dict, field: str, value: Any):
        if not self.parent or not getattr(self.parent, "cache", None):
            return False
        cache = self.parent.cache
        overrides = cache._get_champion_overrides() if hasattr(cache, "_get_champion_overrides") else {}
        key = str(target.get("id") or target.get("slug") or target.get("name") or "").strip().lower()
        if not key:
            return False
        current = overrides.get(key) or {}
        if field == "aliases":
            alias_values = [str(v).strip() for v in (current.get("aliases") or []) if str(v).strip()]
            new_value = str(value).strip()
            if new_value and new_value not in alias_values:
                alias_values.append(new_value)
            if alias_values:
                current["aliases"] = alias_values
            else:
                current.pop("aliases", None)
        elif field == "shortname":
            new_value = str(value).strip()
            if new_value:
                current["shortname"] = new_value
            else:
                current.pop("shortname", None)
        if current:
            overrides[key] = current
        else:
            overrides.pop(key, None)
        if hasattr(cache, "_save_champion_overrides"):
            cache._save_champion_overrides(overrides)
        return True

    def _remove_champion_metadata(self, target: dict, field: str, value: Any):
        if not self.parent or not getattr(self.parent, "cache", None):
            return False
        cache = self.parent.cache
        overrides = cache._get_champion_overrides() if hasattr(cache, "_get_champion_overrides") else {}
        key = str(target.get("id") or target.get("slug") or target.get("name") or "").strip().lower()
        if not key:
            return False
        current = overrides.get(key) or {}
        if field == "aliases":
            alias_values = [str(v).strip() for v in (current.get("aliases") or []) if str(v).strip()]
            filtered = [v for v in alias_values if v != str(value).strip()]
            if filtered:
                current["aliases"] = filtered
            else:
                current.pop("aliases", None)
        elif field == "shortname":
            current.pop("shortname", None)
        if current:
            overrides[key] = current
        else:
            overrides.pop(key, None)
        if hasattr(cache, "_save_champion_overrides"):
            cache._save_champion_overrides(overrides)
        return True

    @commands.group(name="champ", aliases=["champions"])
    async def champ(self, ctx):
        """Champion commands: search, abilities, info."""

    @champ.group(name="set")
    async def champ_set(self, ctx, property_name: str, champion_ref: str, value: str):
        """Set metadata on a champion (admin only): alias or shortname."""
        if not self._champion_admin_guard(ctx):
            await safe_send_ctx(ctx, "Champion metadata management is restricted to the CollectorDevTeam role or configured champion-admin entitlements.")
            return

        if property_name.lower() not in {"alias", "shortname"}:
            await safe_send_ctx(ctx, "Use `///champ set alias <Champion> <alias>` or `///champ set shortname <Champion> <shortname>`.")
            return

        cache = getattr(self.parent, "cache", None) if getattr(self, "parent", None) else None
        if not cache:
            await safe_send_ctx(ctx, "Champion cache unavailable.")
            return

        champion = self._resolve_champion_record(cache, champion_ref)
        if not champion:
            await safe_send_ctx(ctx, f"Champion `{champion_ref}` not found.")
            return

        normalized = str(value).strip()
        if not normalized:
            await safe_send_ctx(ctx, "Value cannot be empty.")
            return

        kind = property_name.lower()
        for candidate in (cache.get_all_champions() or []):
            if not isinstance(candidate, dict) or candidate is champion:
                continue
            if kind == "alias":
                aliases = candidate.get("aliases") or []
                if any(str(a).strip().lower() == normalized.lower() for a in aliases):
                    await safe_send_ctx(ctx, f"Alias `{normalized}` is already assigned to another champion.")
                    return
                override_map = cache._get_champion_overrides() if hasattr(cache, "_get_champion_overrides") else {}
                for meta in override_map.values():
                    if isinstance(meta, dict):
                        for alias in (meta.get("aliases") or []):
                            if str(alias).strip().lower() == normalized.lower():
                                await safe_send_ctx(ctx, f"Alias `{normalized}` is already assigned to another champion.")
                                return
            else:
                short = candidate.get("shortname")
                if short and str(short).strip().lower() == normalized.lower():
                    await safe_send_ctx(ctx, f"Shortname `{normalized}` is already assigned to another champion.")
                    return
                override_map = cache._get_champion_overrides() if hasattr(cache, "_get_champion_overrides") else {}
                for meta in override_map.values():
                    if isinstance(meta, dict) and str(meta.get("shortname") or "").strip().lower() == normalized.lower():
                        await safe_send_ctx(ctx, f"Shortname `{normalized}` is already assigned to another champion.")
                        return

        if kind == "alias":
            aliases = list(champion.get("aliases") or [])
            if normalized.lower() in {str(a).strip().lower() for a in aliases}:
                await safe_send_ctx(ctx, f"Alias `{normalized}` is already set on `{champion.get('name') or champion.get('slug')}`.")
                return
            aliases.append(normalized)
            champion["aliases"] = aliases
            self._save_champion_metadata(champion, "aliases", normalized)
            await safe_send_ctx(ctx, f"Added alias `{normalized}` to `{champion.get('name') or champion.get('slug')}`.")
        else:
            champion["shortname"] = normalized
            self._save_champion_metadata(champion, "shortname", normalized)
            await safe_send_ctx(ctx, f"Added shortname `{normalized}` to `{champion.get('name') or champion.get('slug')}`.")

    @champ.group(name="remove")
    async def champ_remove(self, ctx, property_name: str, value: str):
        """Remove a champion alias or shortname (admin only)."""
        if not self._champion_admin_guard(ctx):
            await safe_send_ctx(ctx, "Champion metadata management is restricted to the CollectorDevTeam role or configured champion-admin entitlements.")
            return

        if property_name.lower() not in {"alias", "shortname"}:
            await safe_send_ctx(ctx, "Use `///champ remove alias <alias>` or `///champ remove shortname <shortname>`.")
            return

        cache = getattr(self.parent, "cache", None) if getattr(self, "parent", None) else None
        if not cache:
            await safe_send_ctx(ctx, "Champion cache unavailable.")
            return

        value_norm = str(value).strip()
        kind = property_name.lower()
        for champion in (cache.get_all_champions() or []):
            if not isinstance(champion, dict):
                continue
            if kind == "alias":
                aliases = champion.get("aliases") or []
                if any(str(a).strip().lower() == value_norm.lower() for a in aliases):
                    champion["aliases"] = [a for a in aliases if str(a).strip().lower() != value_norm.lower()]
                    self._remove_champion_metadata(champion, "aliases", value_norm)
                    await safe_send_ctx(ctx, f"Removed alias `{value_norm}` from `{champion.get('name') or champion.get('slug')}`.")
                    return
            else:
                if str(champion.get("shortname") or "").strip().lower() == value_norm.lower():
                    champion["shortname"] = None
                    self._remove_champion_metadata(champion, "shortname", value_norm)
                    await safe_send_ctx(ctx, f"Removed shortname `{value_norm}` from `{champion.get('name') or champion.get('slug')}`.")
                    return

        override_map = cache._get_champion_overrides() if hasattr(cache, "_get_champion_overrides") else {}
        for meta in override_map.values():
            if not isinstance(meta, dict):
                continue
            if kind == "alias":
                aliases = meta.get("aliases") or []
                if any(str(a).strip().lower() == value_norm.lower() for a in aliases):
                    meta["aliases"] = [a for a in aliases if str(a).strip().lower() != value_norm.lower()]
                    if not meta["aliases"]:
                        meta.pop("aliases", None)
                    cache._save_champion_overrides(override_map)
                    await safe_send_ctx(ctx, f"Removed alias `{value_norm}` from override metadata.")
                    return
            else:
                short = str(meta.get("shortname") or "").strip()
                if short.lower() == value_norm.lower():
                    meta.pop("shortname", None)
                    cache._save_champion_overrides(override_map)
                    await safe_send_ctx(ctx, f"Removed shortname `{value_norm}` from override metadata.")
                    return

        await safe_send_ctx(ctx, f"No champion `{property_name}` matched `{value_norm}`.")

    @champ.command(name="search")
    async def champ_search(self, ctx, *items: str):
        """Search champions with optional filters or explicit tokens."""
        if not await self._require_parent(ctx):
            return

        raw = " ".join(items or "").strip()
        cache = getattr(self.parent, "cache", None)
        try:
            entries, filters = parse_query(raw, cache=cache)
        except Exception:
            entries, filters = [], {"raw_text": raw}

        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        try:
            pager = await Champions.make_champion_pager(self.parent, ctx, raw_input=raw, parsed_filters=parsed_filters, author_for_controls=ctx.author)
        except Exception:
            pager = None

        if pager:
            try:
                brand_view = Embed.brand_view()
                if hasattr(pager, "add_item"):
                    for item in getattr(brand_view, "children", []):
                        try:
                            pager.add_item(item)
                        except Exception:
                            continue
            except Exception:
                pass
            try:
                await pager.start(ctx)
                return
            except Exception:
                log.exception("Failed to start pager from make_champion_pager")

        try:
            pages = await Champions.get_champion_pages(self.parent, ctx.author, filters=parsed_filters)
        except Exception:
            pages = []

        if not pages:
            try:
                await ctx.send(embed=Embed.embed(ctx.author, title="Champions", description="No champions match your search."))
            except Exception:
                await safe_send_ctx(ctx, "No champions match your search.")
            return

        try:
            pager = PagesMenu(pages, author=ctx.author)
            try:
                brand_view = Embed.brand_view()
                if hasattr(pager, "add_item"):
                    for item in getattr(brand_view, "children", []):
                        try:
                            pager.add_item(item)
                        except Exception:
                            continue
            except Exception:
                pass
            await pager.start(ctx)
            return
        except Exception:
            log.exception("Failed to instantiate/start PagesMenu for champion search")
            try:
                first = pages[0]
                await ctx.send(embed=first)
                return
            except Exception:
                try:
                    titles = []
                    for p in pages[:50]:
                        t = getattr(p, "title", None) if not isinstance(p, dict) else p.get("title")
                        titles.append(t or "Entry")
                    await ctx.send(f"Matches ({len(pages)}): {', '.join(titles)}")
                    return
                except Exception:
                    await safe_send_ctx(ctx, "Failed to display champion search results.")
                    return

    @champ.command(name="abilities")
    async def champ_abilities(self, ctx, *, name: str):
        """Show champion abilities."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            abilities = champ_obj.get("abilities") or champ_obj.get("ability_list") or []
            if not abilities:
                await safe_send_ctx(ctx, "Abilities unavailable.")
                return
            desc_lines = []
            for ability in abilities:
                try:
                    title = ability.get("name") or ability.get("title") or "Ability"
                    text = ability.get("description") or ability.get("desc") or ""
                    desc_lines.append(f"**{title}** — {text}")
                except Exception:
                    continue
            desc = "\n\n".join(desc_lines) or "Abilities unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Abilities", description=desc))
        except Exception:
            log.exception("Failed to render abilities for %s", name)
            await safe_send_ctx(ctx, "Abilities unavailable.")

    @champ.command(name="info")
    async def champ_info(self, ctx, *, name: str):
        """Show basic champion info."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            name_text = champ_obj.get("name") or champ_obj.get("slug") or "Unknown"
            class_name = champ_obj.get("class") or "Unknown"
            tags = ", ".join(champ_obj.get("tags") or []) or "None"
            role = champ_obj.get("role") or champ_obj.get("archetype") or "Unknown"
            desc = f"**Class:** {class_name}\n**Role:** {role}\n**Tags:** {tags}"
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{name_text} — Info", description=desc))
        except Exception:
            log.exception("Failed to render champion info for %s", name)
            await safe_send_ctx(ctx, "Champion info unavailable.")

    @champ.command(name="bio")
    async def champ_bio(self, ctx, *, name: str):
        """Show the biography of the specified champion."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            bio = champ_obj.get("bio") or "Biography unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Biography", description=bio))
        except Exception:
            log.exception("Failed to render champion biography for %s", name)
            await safe_send_ctx(ctx, "Champion biography unavailable.")

    @champ.command(name="synergies")
    async def champ_synergies(self, ctx, *, name: str):
        """Show the synergies of the specified champion."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            synergies = champ_obj.get("synergies") or "Synergies unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Synergies", description=synergies))
        except Exception:
            log.exception("Failed to render champion synergies for %s", name)
            await safe_send_ctx(ctx, "Champion synergies unavailable.")

    @champ.command(name="counters")
    async def champ_counters(self, ctx, *, name: str):
        """Show the counters of the specified champion."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            counters = champ_obj.get("counters") or "Counters unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Counters", description=counters))
        except Exception:
            log.exception("Failed to render champion counters for %s", name)
            await safe_send_ctx(ctx, "Champion counters unavailable.")

    @champ.command(name="signature", aliases=["sig"])
    async def champ_signature(self, ctx, *, name: str):
        """Show the signature ability of the specified champion."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            signature = champ_obj.get("signature") or "Signature ability unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Signature Ability", description=signature))
        except Exception:
            log.exception("Failed to render champion signature ability for %s", name)
            await safe_send_ctx(ctx, "Champion signature ability unavailable.")

    @champ.command(name="stats")
    async def champ_stats(self, ctx, *, name: str):
        """Show the stats of the specified champion."""
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                champ_obj = cache.get_champion(name)
                if not champ_obj:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            stats = champ_obj.get("stats") or "Stats unavailable."
            await ctx.send(embed=Embed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Stats", description=stats))
        except Exception:
            log.exception("Failed to render champion stats for %s", name)
            await safe_send_ctx(ctx, "Champion stats unavailable.")


async def setup(bot):
    bot.add_cog(ChampionsPrefix(bot))
