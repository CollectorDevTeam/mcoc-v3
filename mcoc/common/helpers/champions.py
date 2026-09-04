# Path: mcoc/common/helpers/champions.py
# File-Version: 1.0
# File-Id: 69c6d576-1378-4c30-8030-7e8f3b0d24aa
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: _get_all_champions_from_cache, _normalize_champion_input, _champion_matches_filters
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

"""
Champion helpers: deck-first champion search, filtering, formatting and page construction.

This module centralizes logic previously in prefix/champions.py and provides:
  - champion deck retrieval and safe cache access
  - filtering by name, tags, classes and hargs-like filters
  - formatting lines via format_champion_line
  - chunking results into branded Embed pages
  - convenience pager factory make_champion_pager

Prefix handlers should be thin: call make_champion_pager or get_champion_pages and start the pager.
"""

from typing import Any, Dict, List, Optional, Tuple, Mapping
import logging
import asyncio
from collections import defaultdict

from mcoc.common.components.componentsV2 import CDTEmbed, CDTPagesMenu
from mcoc.common.utilities.formatters import format_champion_line, format_tierlist_champion_line
from mcoc.common.helpers.types import Champion, champion_from_dict, MCOCAPP_TIERS, MCOCAPP_PROPERTIES

CHAMPIONS_FOOTER = " | CollectorDevTeam"

log = logging.getLogger("red.mcoc.champions")


def resolve_champion(cache: Any, champion_ref: Any) -> Optional[Dict[str, Any]]:
    """Resolve a champion from a cache by id/slug/name.

    This keeps the slash layer compatible with the shared helper contract.
    """
    if not cache or champion_ref is None:
        return None

    try:
        direct = cache.get_champion(champion_ref)
        if isinstance(direct, dict):
            return direct
    except Exception:
        pass

    needle = str(champion_ref).strip().lower()
    if not needle:
        return None

    try:
        for champ in (cache.get_all_champions() or []):
            if not isinstance(champ, dict):
                continue
            candidates = [
                champ.get("id"),
                champ.get("slug"),
                champ.get("name"),
                champ.get("title"),
                champ.get("shortname"),
            ]
            candidates.extend(champ.get("aliases") or [])
            for candidate in candidates:
                if candidate is None:
                    continue
                if str(candidate).strip().lower() == needle:
                    return champ
    except Exception:
        log.exception("resolve_champion failed for %s", champion_ref)
    return None


async def safe_respond_interaction(interaction: Any, *, content: Optional[str] = None, embed: Optional[Any] = None, view: Optional[Any] = None, ephemeral: bool = False, followup: bool = False) -> None:
    """Minimal compatibility helper for slash interaction responses."""
    if interaction is None:
        return

    try:
        if followup and hasattr(interaction, "followup"):
            await interaction.followup.send(content=content or "", embed=embed, view=view, ephemeral=ephemeral)
            return

        if hasattr(interaction, "response") and getattr(interaction, "response", None) is not None:
            await interaction.response.send_message(content=content or "", embed=embed, view=view, ephemeral=ephemeral)
            return

        if hasattr(interaction, "followup"):
            await interaction.followup.send(content=content or "", embed=embed, view=view, ephemeral=ephemeral)
            return

        if hasattr(interaction, "channel") and hasattr(interaction.channel, "send"):
            await interaction.channel.send(content=content or "", embed=embed, view=view)
            return
    except Exception:
        log.exception("safe_respond_interaction failed for interaction=%r", interaction)


def lookup_stat(champ: Optional[Mapping[str, Any]], rarity: Any, rank: Any, ascended: Any = 0) -> Optional[Dict[str, Any]]:
    """Return a stat table for a champion at the given rarity/rank/ascension.

    This compatibility helper fills in the contract used by the slash champion commands
    when they build a calcstats embed.
    """
    if not isinstance(champ, Mapping):
        return None
    stats = champ.get("stats") or {}
    try:
        rarity_key = int(rarity)
        rank_key = int(rank)
        asc = int(ascended or 0)
    except Exception:
        return None

    rarity_bucket = stats.get(str(rarity_key), {}) if isinstance(stats, Mapping) else {}
    if not isinstance(rarity_bucket, Mapping):
        rarity_bucket = stats.get(rarity_key, {}) if isinstance(stats, Mapping) else {}
    if not isinstance(rarity_bucket, Mapping):
        return None

    rank_bucket = rarity_bucket.get(str(rank_key), {}) if isinstance(rarity_bucket, Mapping) else {}
    if not isinstance(rank_bucket, Mapping):
        rank_bucket = rarity_bucket.get(rank_key, {}) if isinstance(rarity_bucket, Mapping) else {}
    if not isinstance(rank_bucket, Mapping):
        return None

    if asc and isinstance(rank_bucket, Mapping):
        asc_bucket = rank_bucket.get("ascended", {})
        if isinstance(asc_bucket, Mapping):
            try:
                rank_bucket = asc_bucket.get(str(asc), asc_bucket.get(asc, rank_bucket))
            except Exception:
                rank_bucket = asc_bucket.get(str(asc), rank_bucket)

    if not isinstance(rank_bucket, Mapping):
        return None

    return {
        "attack": rank_bucket.get("attack") or rank_bucket.get("ATK") or rank_bucket.get("atk") or rank_bucket.get("attack_rating"),
        "health": rank_bucket.get("health") or rank_bucket.get("HP") or rank_bucket.get("hp") or rank_bucket.get("health_rating"),
        "speed": rank_bucket.get("speed") or rank_bucket.get("SPD") or rank_bucket.get("spd"),
        "crit": rank_bucket.get("crit") or rank_bucket.get("crit_rating"),
        "armor": rank_bucket.get("armor") or rank_bucket.get("armour") or rank_bucket.get("armor_rating"),
        "resist": rank_bucket.get("resist") or rank_bucket.get("resistance") or rank_bucket.get("resist_rating"),
    }


def _titleize_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return "Ability"
    return token.replace("_", " ").replace("-", " ").title()


def _resolve_glossary_term(cache: Any, term: Any) -> Optional[Dict[str, Any]]:
    if not cache or not term:
        return None
    try:
        getter = getattr(cache, "get_glossary_term", None)
        if callable(getter):
            item = getter(term)
            if isinstance(item, dict):
                return item
    except Exception:
        pass
    return None


def _resolve_champion_name(cache: Any, champion_id: Any) -> str:
    raw = str(champion_id or "").strip()
    if not raw:
        return "Unknown"
    if cache:
        try:
            champ = cache.get_champion(raw)
            if isinstance(champ, dict):
                return str(champ.get("name") or champ.get("slug") or raw)
        except Exception:
            pass
    return _titleize_token(raw)


def extract_champion_synergies(champ: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ability in (champ.get("abilities") or []):
        if not isinstance(ability, dict):
            continue
        if ability.get("source") == "synergy" or ability.get("synergy_with") or ability.get("note"):
            out.append(ability)
    return out


def build_champion_ability_lines(champ: Mapping[str, Any], cache: Any = None) -> List[str]:
    lines: List[str] = []
    for ability in (champ.get("abilities") or champ.get("ability_list") or []):
        if not isinstance(ability, dict):
            label = _titleize_token(ability)
            lines.append(f"**{label}**")
            continue
        raw_name = ability.get("name") or ability.get("id") or ability.get("title") or "Ability"
        glossary = _resolve_glossary_term(cache, raw_name)
        title = glossary.get("word") if glossary else _titleize_token(raw_name)
        description = ability.get("description") or ability.get("desc") or ability.get("note") or (glossary.get("description") if glossary else "")
        suffix_parts: List[str] = []
        ability_type = ability.get("type")
        if ability_type and ability_type != "full":
            suffix_parts.append(str(ability_type))
        if ability.get("source") == "synergy":
            suffix_parts.append("synergy")
        suffix = f" [{', '.join(suffix_parts)}]" if suffix_parts else ""
        if description:
            lines.append(f"**{title}**{suffix} — {description}")
        else:
            lines.append(f"**{title}**{suffix}")
    return lines


def build_champion_synergy_lines(champ: Mapping[str, Any], cache: Any = None) -> List[str]:
    lines: List[str] = []
    for synergy in extract_champion_synergies(champ):
        raw_name = synergy.get("name") or synergy.get("id") or "Synergy"
        glossary = _resolve_glossary_term(cache, raw_name)
        title = glossary.get("word") if glossary else _titleize_token(raw_name)
        partners = [_resolve_champion_name(cache, partner) for partner in (synergy.get("synergy_with") or [])]
        if partners:
            partner_text = f" With: {', '.join(partners)}."
        elif synergy.get("source") == "synergy" or synergy.get("note"):
            partner_text = " Partner data unavailable from source."
        else:
            partner_text = ""
        description = synergy.get("note") or (glossary.get("description") if glossary else "") or ""
        if description:
            lines.append(f"**{title}** — {description}{partner_text}")
        elif partner_text:
            lines.append(f"**{title}** —{partner_text}")
        else:
            lines.append(f"**{title}**")
    return lines


# -----------------------------
# Low-level cache helpers
# -----------------------------
def _get_all_champions_from_cache(core: Any) -> List[Dict[str, Any]]:
    """
    Safely retrieve the full champion deck from core.cache.
    Returns an empty list on any failure.
    """
    try:
        cache = getattr(core, "cache", None)
        if not cache:
            return []
        # prefer the raw list/dict getter for compatibility
        getter = getattr(cache, "get_all_champions", None) or getattr(cache, "all_champions", None)
        if callable(getter):
            return getter() or []
    except Exception:
        log.exception("Failed to retrieve champions from cache")
    return []


# -----------------------------
# Normalization helpers
# -----------------------------
def _normalize_champion_input(champ_obj: Optional[Mapping[str, Any]]) -> Optional[Champion]:
    """
    Convert a raw champion dict (or None) into a Champion dataclass.
    If champ_obj is already a Champion instance, return it unchanged.
    """
    if champ_obj is None:
        return None
    if isinstance(champ_obj, Champion):
        return champ_obj
    try:
        return champion_from_dict(champ_obj)
    except Exception:
        return None


# -----------------------------
# Filtering helpers
# -----------------------------
def _normalize_champion_token(value: Any) -> str:
    """Collapse separators so tag and immunity names compare consistently."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _champion_matches_filters(champ: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Return True if champion object matches the provided filters.
    Supported filters:
      - name: substring match against name or slug
      - tags: list of tag substrings (all must match)
      - classes: list of class names (any match)
    """
    try:
        if not filters:
            return True

        name_filter = (filters.get("name") or "").strip().lower() if filters.get("name") else None
        tag_filters = [str(t).lower() for t in (filters.get("tags") or [])]
        class_filters = [c.lower() for c in (filters.get("classes") or [])]

        # name/slug match
        if name_filter:
            name = (str(champ.get("name") or "") + " " + str(champ.get("slug") or "")).lower()
            if name_filter not in name:
                return False

        # class match
        if class_filters:
            champ_class = (champ.get("class") or champ.get("class_name") or "").lower()
            if champ_class not in class_filters:
                return False

        # tags/immunities: every requested token must be present somewhere on the champion
        if tag_filters:
            champion_tokens: List[str] = []
            for tag in (champ.get("tags") or []):
                champion_tokens.append(_normalize_champion_token(tag))
            for immunity in (champ.get("immunities") or []):
                if isinstance(immunity, dict):
                    for key in ("name", "id", "slug"):
                        val = immunity.get(key)
                        if val:
                            champion_tokens.append(_normalize_champion_token(val))
                else:
                    champion_tokens.append(_normalize_champion_token(immunity))
            champion_tokens = [t for t in champion_tokens if t]
            for tf in tag_filters:
                tf_norm = _normalize_champion_token(tf)
                if not tf_norm:
                    continue
                ok = False
                for ct in champion_tokens:
                    if tf_norm == ct or tf_norm in ct or ct in tf_norm:
                        ok = True
                        break
                if not ok:
                    return False

        return True
    except Exception:
        return False


def _normalized_tier_key(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Unranked"
    return raw


def _tierlist_tier_order() -> List[str]:
    ordered = list(MCOCAPP_TIERS.keys())
    seen = set(ordered)
    for key in ["S+", "S", "A", "B", "C", "D", "F"]:
        if key not in seen:
            ordered.append(key)
    return ordered


def _tierlist_sort_key(champion: Dict[str, Any]) -> Tuple[float, str]:
    name = str(champion.get("name") or champion.get("slug") or "").strip().lower()
    score = champion.get("score")
    try:
        score_value = float(score)
    except Exception:
        score_value = 0.0
    return (-score_value, name)


def build_tier_pages(champions: List[Dict[str, Any]], *, filters: Optional[Dict[str, Any]] = None, page_size: int = 10, tier_order: Optional[List[str]] = None, tier_colors: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Build paged tier-grouped output from a tierlist-shaped champion list."""
    filtered = []
    for champion in champions or []:
        if not isinstance(champion, dict):
            continue
        if not _champion_matches_filters(champion, filters or {}):
            continue
        filtered.append(champion)

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for champion in filtered:
        tier_name = _normalized_tier_key(champion.get("tier") or "Unranked")
        grouped[tier_name].append(champion)

    order = tier_order or _tierlist_tier_order()
    ordered_groups: List[Dict[str, Any]] = []
    for tier in order:
        items = sorted(grouped.get(tier, []), key=_tierlist_sort_key)
        if not items:
            continue
        ordered_groups.append({
            "tier": tier,
            "title": MCOCAPP_TIERS.get(tier, {}).get("name", f"{tier} TIER"),
            "color": tier_colors.get(tier, MCOCAPP_TIERS.get(tier, {}).get("color", "#ffffff")) if tier_colors else MCOCAPP_TIERS.get(tier, {}).get("color", "#ffffff"),
            "items": items,
        })

    leftovers = sorted(
        [(tier, items) for tier, items in grouped.items() if tier not in {g["tier"] for g in ordered_groups}],
        key=lambda pair: (pair[0] == "Unranked", pair[0]),
    )
    for tier, items in leftovers:
        ordered_groups.append({
            "tier": tier,
            "title": MCOCAPP_TIERS.get(tier, {}).get("name", f"{tier} TIER"),
            "color": tier_colors.get(tier, MCOCAPP_TIERS.get(tier, {}).get("color", "#ffffff")) if tier_colors else MCOCAPP_TIERS.get(tier, {}).get("color", "#ffffff"),
            "items": sorted(items, key=_tierlist_sort_key),
        })

    page_groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_len = 0
    for group in ordered_groups:
        block = [f"**{group['title']}**"]
        for champ in group["items"]:
            block.append(format_tierlist_champion_line(champ))
        block_text = "\n".join(block)
        if current and (current_len + len(block_text) + 2 > 1800 or len(current) >= page_size):
            page_groups.append(current)
            current = []
            current_len = 0
        current.append(group)
        current_len += len(block_text)
    if current:
        page_groups.append(current)

    pages: List[Dict[str, Any]] = []
    for index, groups in enumerate(page_groups, start=1):
        page_color = groups[0]["color"] if groups else "#ffffff"
        pages.append({
            "title": "Tierlist",
            "color": page_color,
            "groups": groups,
            "page": index,
            "page_count": len(page_groups),
        })

    if not pages:
        return [{"title": "Tierlist", "color": "#ffffff", "groups": [], "page": 1, "page_count": 1}]
    return pages


# -----------------------------
# Build champion lines and pages
# -----------------------------
def _format_champion_entry(champ: Dict[str, Any], default_entry: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a canonical entry dict for formatting and return a formatted line using format_champion_line.
    default_entry may supply rarity/rank/sig/ascended when the user provided explicit hargs.
    """
    try:
        entry = {
            "champion": champ.get("slug") or champ.get("id") or champ.get("name"),
            "rarity": int(default_entry.get("rarity")) if default_entry and default_entry.get("rarity") is not None else int(champ.get("stars") or champ.get("rarity") or 6),
            "rank": int(default_entry.get("rank")) if default_entry and default_entry.get("rank") is not None else 1,
            "sig": int(default_entry.get("sig")) if default_entry and default_entry.get("sig") is not None else 0,
            "ascended": int(default_entry.get("ascended")) if default_entry and default_entry.get("ascended") is not None else 0,
            "tags": default_entry.get("tags") if default_entry and default_entry.get("tags") is not None else (champ.get("tags") or []),
            "raw": champ.get("name") or champ.get("slug"),
        }
        # include class metadata for formatter
        if champ.get("class"):
            entry["class"] = champ.get("class")

        # Normalize champ to Champion dataclass when possible and pass to formatter
        champ_obj = _normalize_champion_input(champ)

        # call formatter (defensive about signature)
        try:
            return format_champion_line(champ_obj, entry)
        except TypeError:
            # older signature fallback (if any)
            return format_champion_line(champ, entry)  # type: ignore
    except Exception:
        log.exception("Failed to format champion entry for %s", champ.get("slug") if champ else "<unknown>")
        # fallback simple line
        try:
            return f"**{champ.get('name') or champ.get('slug') or 'Unknown'}**"
        except Exception:
            return "Unknown"


async def build_tierlist_embed_pages(author: Any, pages: List[Dict[str, Any]]) -> List[Any]:
    """Translate a tierlist page payload into Discord embed objects."""
    out: List[Any] = []
    for idx, page in enumerate(pages, start=1):
        embed = CDTEmbed.embed(author, title=f"Tierlist ({idx}/{len(pages)})", color=page.get("color"), description="")
        for group in page.get("groups", []) or []:
            lines = []
            for champion in group.get("items", []) or []:
                lines.append(format_tierlist_champion_line(champion))
            if lines:
                CDTEmbed.add_field(author, embed, name=group.get("title", "Tier"), value="\n".join(lines), inline=False)
        if not getattr(embed, "fields", None):
            embed.description = "No champions match your tierlist filters."
        out.append(embed)
    return out


async def build_champion_pages(core: Any, ctx_or_author: Any, filters: Optional[Dict[str, Any]] = None, *, lines_per_page: int = 15, char_limit: int = 1800) -> List[Any]:
    """
    Build a list of Embed pages for champion search results.

    Parameters:
      - core: bot/core object (used to access cache)
      - ctx_or_author: Context or author-like object used for branding (author name/avatar)
      - filters: dict from parse_query (name, tags, classes, raw_text)
      - lines_per_page, char_limit: pagination controls

    Returns:
      - List of Embed embed objects (normal path) or list of dict fallbacks on catastrophic failure.
    """
    # normalize author_for_embed
    author_for_embed = None
    try:
        if ctx_or_author is None:
            author_for_embed = None
        elif hasattr(ctx_or_author, "author"):
            author_for_embed = ctx_or_author.author
        else:
            author_for_embed = ctx_or_author
    except Exception:
        author_for_embed = None

    try:
        deck = _get_all_champions_from_cache(core)
        if not deck:
            # no champions available
            try:
                emb = CDTEmbed.embed(author_for_embed, title="Champions", description="No champion data available.", footer_text=f"Page 1 of 1{CHAMPIONS_FOOTER}")
                return [emb]
            except Exception:
                return [{"title": "Champions", "description": "No champion data available.", "footer": {"text": f"Page 1 of 1{CHAMPIONS_FOOTER}"}}]

        # apply deck-first filtering
        filt = filters or {}
        explicit = filt.get("explicit_entries") if isinstance(filt, dict) else None

        matched: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []  # (champ_obj, default_entry)
        if explicit:
            # For each explicit entry, try to find matching champion in deck by slug or name
            slug_map = {}
            for c in deck:
                try:
                    slug_map[str(c.get("slug") or c.get("id") or "").lower()] = c
                    slug_map[str((c.get("name") or "").lower())] = c
                except Exception:
                    continue
            for ent in explicit:
                try:
                    key = str(ent.get("champion") or "").lower()
                    champ_obj = slug_map.get(key)
                    if not champ_obj:
                        # try contains/startswith fallback
                        for c in deck:
                            name = (c.get("name") or "").lower()
                            if key in name or name.startswith(key):
                                champ_obj = c
                                break
                    if champ_obj:
                        matched.append((champ_obj, ent))
                except Exception:
                    continue
        else:
            # No explicit entries: filter entire deck
            for c in deck:
                try:
                    if _champion_matches_filters(c, filt):
                        matched.append((c, None))
                except Exception:
                    continue

        if not matched:
            try:
                emb = CDTEmbed.embed(author_for_embed, title="Champions", description="No champions match your search.", footer_text=f"Page 1 of 1{CHAMPIONS_FOOTER}")
                return [emb]
            except Exception:
                return [{"title": "Champions", "description": "No champions match your search.", "footer": {"text": f"Page 1 of 1{CHAMPIONS_FOOTER}"}}]

        # Build formatted lines
        lines: List[str] = []
        for champ_obj, default_entry in matched:
            try:
                line = _format_champion_entry(champ_obj, default_entry)
                lines.append(line)
            except Exception:
                continue

        # Chunk into pages
        page_texts: List[str] = []
        cur: List[str] = []
        cur_len = 0
        for line in lines:
            if len(cur) >= lines_per_page or (cur_len + len(line) + 1) > char_limit:
                page_texts.append("\n".join(cur))
                cur = []
                cur_len = 0
            cur.append(line)
            cur_len += len(line) + 1
        if cur:
            page_texts.append("\n".join(cur))

        # Build title and embeds
        title = f"Champions ({len(matched)})"
        embed_pages: List[Any] = []
        try:
            for i, ptext in enumerate(page_texts):
                footer = f"Page {i+1} of {len(page_texts)}{CHAMPIONS_FOOTER}"
                emb = CDTEmbed.embed(author_for_embed, title=title, description=ptext, footer_text=footer)
                try:
                    CDTEmbed.set_footer(author_for_embed, emb, text=footer)
                except Exception:
                    pass
                embed_pages.append(emb)
            return embed_pages
        except Exception:
            out = []
            for i, ptext in enumerate(page_texts):
                out.append({"title": title, "description": ptext, "footer": {"text": f"Page {i+1} of {len(page_texts)}{CHAMPIONS_FOOTER}"}})
            return out

    except Exception:
        log.exception("Failed to build champion pages")
        return []


async def get_champion_pages(core: Any, ctx_or_author: Any, filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Public wrapper that returns embed pages for champion search results.
    Guarantees embed objects where possible.
    """
    pages = await build_champion_pages(core, ctx_or_author, filters=filters)
    out: List[Any] = []
    for p in pages:
        if isinstance(p, dict):
            try:
                emb = CDTEmbed.embed(ctx_or_author, title=p.get("title"), description=p.get("description"), footer_text=(p.get("footer") or {}).get("text"))
                out.append(emb)
            except Exception:
                out.append(p)
        else:
            out.append(p)
    return out


async def make_champion_pager(core: Any, ctx_or_author: Any, *, raw_input: Optional[str] = None, parsed_filters: Optional[Dict[str, Any]] = None, author_for_controls: Optional[Any] = None) -> Optional[CDTPagesMenu]:
    """
    Convenience wrapper that builds champion pages and returns a ready PagesMenu with brand buttons merged.
    """
    try:
        parsed = parsed_filters or {}
        if not parsed and raw_input:
            try:
                # lazy import to avoid circulars
                from ..utilities.query_parser import parse_query
                cache = getattr(core, "cache", None)
                entries, filters = parse_query(raw_input, cache=cache)
                parsed = {}
                if entries:
                    parsed["explicit_entries"] = entries
                if isinstance(filters, dict):
                    parsed.update(filters)
            except Exception:
                parsed = {}

        pages = await get_champion_pages(core, ctx_or_author, filters=parsed)
        if not pages:
            return None

        # Instantiate pager
        try:
            pager = CDTPagesMenu(pages, author=(author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author)))
        except TypeError:
            try:
                pager = CDTPagesMenu(pages, ctx_or_author)
            except TypeError:
                try:
                    pager = CDTPagesMenu(pages)
                    if hasattr(pager, "author"):
                        try:
                            pager.author = (author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author))
                        except Exception:
                            pass
                except Exception:
                    return None

        # Merge brand buttons if available
        try:
            brand_view = CDTEmbed.brand_view()
            if hasattr(pager, "add_item"):
                for item in getattr(brand_view, "children", []):
                    try:
                        pager.add_item(item)
                    except Exception:
                        continue
        except Exception:
            pass

        return pager
    except Exception:
        log.exception("make_champion_pager failed")
        return None

# -----------------------------
# Footer helper (reusable)
# -----------------------------
def add_page_footers(pages: List[Any], author_for_embed: Any = None) -> List[Any]:
    """
    Ensure each embed page has a footer with page numbering.
    Accepts embed objects or dict fallbacks.
    """
    out: List[Any] = []
    total = len(pages)
    for i, p in enumerate(pages):
        try:
            if isinstance(p, dict):
                emb = CDTEmbed.embed(author_for_embed, title=p.get("title", "Champions"), description=p.get("description", ""))
            else:
                emb = p
            try:
                base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
                footer_text = f"{base} • Page {i+1} of {total}" if base else f"Page {i+1} of {total}"
                footer_text += f"{CHAMPIONS_FOOTER}"
                CDTEmbed.set_footer(author_for_embed, emb, text=footer_text)
            except Exception:
                try:
                    CDTEmbed.set_footer(author_for_embed, emb, text=f"Page {i+1} of {total}{CHAMPIONS_FOOTER}")
                except Exception:
                    pass
            out.append(emb)
        except Exception:
            out.append(p)
    return out
