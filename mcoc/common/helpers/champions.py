# Path: mcoc/common/helpers/champions.py
# File-Version: 1.0
# File-Id: 69c6d576-1378-4c30-8030-7e8f3b0d24aa
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: _get_all_champions_from_cache, _normalize_champion_input, _champion_matches_filters
# Last-Modified: 2026-09-01
# Used-By: mcoc/common/components/componentsV2.py, mcoc/common/helpers/types.py, mcoc/common/utilities/formatters.py, mcoc/common/utilities/query_parser.py
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
import re
from collections import defaultdict

from mcoc.common.components.componentsV2 import CDTEmbed, CDTPagesMenu, discord
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
    """Collapse separators so filter names compare consistently across tag, ability, and immunity sources."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _iter_champion_filter_values(value: Any) -> List[str]:
    """Flatten a champion field into the canonical filter vocabulary used by the shared matcher."""
    flattened: List[str] = []
    if value is None:
        return flattened
    if isinstance(value, Mapping):
        for key in ("name", "id", "slug", "type", "class", "class_name", "tier", "title", "value"):
            if key in value and value.get(key) not in (None, ""):
                flattened.extend(_iter_champion_filter_values(value.get(key)))
        return flattened
    if isinstance(value, (list, tuple, set)):
        for item in value:
            flattened.extend(_iter_champion_filter_values(item))
        return flattened
    text = str(value).strip()
    if text:
        flattened.append(text)
    return flattened


def _champion_filter_tokens(champ: Dict[str, Any]) -> List[str]:
    """Return the normalized champion filter vocabulary: class, tier, tags, abilities, immunities, inflicts."""
    tokens: List[str] = []
    for source in (
        champ.get("class"),
        champ.get("class_name"),
        champ.get("tier"),
        champ.get("tags"),
        champ.get("abilities"),
        champ.get("immunities"),
        champ.get("inflicts"),
    ):
        if isinstance(source, Mapping):
            # Ability and immunity objects are represented as dicts whose canonical name is stored in `name`.
            for key in ("name", "id", "slug", "title", "type", "value"):
                if key in source and source.get(key) not in (None, ""):
                    tokens.extend(_iter_champion_filter_values(source.get(key)))
            continue
        for item in _iter_champion_filter_values(source):
            token = _normalize_champion_token(item)
            if token:
                tokens.append(token)
    return tokens


def _bucket_matches(bucket: List[str], accepted: List[str]) -> bool:
    """Each bucket uses multi-select OR semantics, while the whole filter set uses AND semantics across buckets."""
    if not accepted:
        return True
    accepted_tokens = {_normalize_champion_token(value) for value in accepted if _normalize_champion_token(value)}
    if not accepted_tokens:
        return True
    return any(token in {_normalize_champion_token(v) for v in bucket if _normalize_champion_token(v)} for token in accepted_tokens)


def _champion_matches_filters(champ: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Return True if champion object matches the provided filters.

    A filter token may match any of the champion's canonical vocabularies: class,
    tier, tag, ability, immunity, or inflicted effect. This keeps the shared
    filtering layer consistent across champion search, roster filtering, and the
    no-args picker flow.
    """
    try:
        if not filters:
            return True

        name_filter = (filters.get("name") or "").strip().lower() if filters.get("name") else None
        if name_filter:
            name = (str(champ.get("name") or "") + " " + str(champ.get("slug") or "")).lower()
            if name_filter not in name:
                return False

        requested_tokens: List[str] = []
        for key in ("tags", "classes", "abilities", "immunities", "inflicts", "tiers", "rarities"):
            for value in (filters.get(key) or []):
                token = str(value).lower().strip()
                if token:
                    requested_tokens.append(token)

        if not requested_tokens:
            return True

        champion_tokens = _champion_filter_tokens(champ)
        champion_tokens_norm = {_normalize_champion_token(token) for token in champion_tokens if _normalize_champion_token(token)}
        for requested in requested_tokens:
            wanted = _normalize_champion_token(requested)
            if not wanted:
                continue
            matches = False
            for candidate in champion_tokens_norm:
                if wanted == candidate:
                    matches = True
                    break
                if len(wanted) > 1 and len(candidate) > 1 and (candidate.startswith(wanted) or wanted.startswith(candidate)):
                    matches = True
                    break
            if not matches:
                # allow direct class/tier value checks to remain compatible with legacy filters
                bucket_values = []
                for key in ("class", "tier"):
                    value = champ.get(key) or champ.get("class_name") if key == "class" else champ.get(key)
                    if value is not None:
                        bucket_values.append(str(value).lower())
                if wanted and bucket_values and any(wanted == _normalize_champion_token(v) for v in bucket_values):
                    continue
                return False

        return True
    except Exception:
        return False


def _collect_champion_filter_catalog(core: Any) -> List[Any]:
    """Build a canonical live catalog of filter tokens from the cache-backed champion deck."""
    catalog: List[Any] = []
    if core is None:
        return catalog

    try:
        cache = getattr(core, "cache", None)
        if cache is None:
            return catalog
        getter = getattr(cache, "get_all_champions", None) or getattr(cache, "all_champions", None)
        champions = getter() if callable(getter) else []
    except Exception:
        return catalog

    if not isinstance(champions, list):
        return catalog

    seen: set = set()
    for champ in champions:
        if not isinstance(champ, dict):
            continue

        for bucket_key, bucket in (
            ("tags", champ.get("tags") or []),
            ("abilities", champ.get("abilities") or []),
            ("immunities", champ.get("immunities") or []),
            ("inflicts", champ.get("inflicts") or []),
        ):
            for item in _iter_champion_filter_values(bucket):
                token = str(item or "").strip().lower()
                if not token:
                    continue
                token = token.strip("#")
                if token not in seen:
                    seen.add(token)
                    catalog.append({"value": token, "type": bucket_key})

        class_name = str(champ.get("class") or champ.get("class_name") or "").strip().lower()
        if class_name and class_name not in seen:
            seen.add(class_name)
            catalog.append({"value": class_name, "type": "class"})

        tier_name = str(champ.get("tier") or "").strip().lower()
        if tier_name:
            cleaned = tier_name.replace("*", "").replace("★", "").replace("star", "").replace("stars", "").strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                catalog.append({"value": cleaned, "type": "tier"})

    return catalog


def build_filter_picker_sections(catalog: Optional[List[Any]] = None) -> Dict[str, List[str]]:
    """Split the live filter catalog into the compact selector buckets used by the filter picker.

    Discord Select components do not provide text autocomplete. To keep the picker usable,
    we group filters by semantic buckets instead of exposing a single 16-page list.
    """
    sections: Dict[str, List[str]] = {
        "inflicts": [],
        "immune_to": [],
        "classes": [],
        "abilities": [],
        "tiers": [],
        "tags": [],
    }
    seen: Dict[str, set] = {key: set() for key in sections}

    def add_value(section: str, value: Any) -> None:
        token = str(value or "").strip().lower()
        token = token.strip("#")
        if not token or token in seen[section]:
            return
        seen[section].add(token)
        sections[section].append(token)

    for item in catalog or []:
        if not isinstance(item, Mapping):
            continue
        raw_value = item.get("value")
        if raw_value is None:
            raw_value = item.get("label")
        if raw_value is None:
            raw_value = item.get("name")
        kind = str(item.get("type") or "").strip().lower()
        if kind in {"inflict", "inflicts"}:
            add_value("inflicts", raw_value)
            continue
        if kind in {"immunity", "immunities", "immune_to"}:
            add_value("immune_to", raw_value)
            continue
        if kind in {"class", "classes"}:
            add_value("classes", raw_value)
            continue
        if kind in {"ability", "abilities"}:
            add_value("abilities", raw_value)
            continue
        if kind in {"tier", "tiers", "rarity", "rarities"}:
            add_value("tiers", raw_value)
            continue
        if kind in {"tag", "tags"}:
            add_value("tags", raw_value)
            continue

    for key in list(sections):
        if key == "classes":
            ordered = ["mystic", "cosmic", "tech", "mutant", "skill", "science"]
            sections[key] = sorted(set(sections[key]), key=lambda token: (token not in ordered, ordered.index(token) if token in ordered else 9999, token))
        elif key == "tiers":
            sections[key] = sorted(set(sections[key]), key=lambda token: (not str(token).isdigit(), int(token) if str(token).isdigit() else 9999, str(token)))
        else:
            sections[key] = sorted(set(sections[key]))
    return sections


def _filter_picker_category_label(category: str) -> str:
    labels = {
        "inflicts": "Inflicts",
        "immune_to": "Immune To",
        "classes": "Class",
        "abilities": "Abilities",
        "tiers": "Tier",
    }
    return labels.get(category, _titleize_token(category))


def _filter_picker_page_values(values: List[str], page_index: int, *, page_size: int = 25) -> Tuple[List[str], int]:
    ordered = list(dict.fromkeys(values))
    if not ordered:
        return [], 1
    total_pages = max(1, (len(ordered) + page_size - 1) // page_size)
    current_page = max(0, min(page_index, total_pages - 1))
    start = current_page * page_size
    end = start + page_size
    return ordered[start:end], total_pages


def build_filter_flow_state(filters: Optional[Dict[str, Any]] = None, *, catalog: Optional[List[Any]] = None) -> Dict[str, List[str]]:
    """Reduce the current filter dict into deduplicated filter/class/tier buckets for the multi-step UI."""
    raw = dict(filters or {})
    filter_values: List[str] = []
    classes: List[str] = []
    tiers: List[str] = []
    seen_filters: set = set()
    seen_classes: set = set()
    seen_tiers: set = set()

    def add_filter(value: Any) -> None:
        token = str(value or "").strip().lower()
        if not token:
            return
        token = token.strip("#")
        if token not in seen_filters:
            seen_filters.add(token)
            filter_values.append(token)

    def add_class(value: Any) -> None:
        token = str(value or "").strip().lower()
        if not token:
            return
        if token not in seen_classes:
            seen_classes.add(token)
            classes.append(token)

    def add_tier(value: Any) -> None:
        token = str(value or "").strip().lower()
        if not token:
            return
        if token.isdigit():
            cleaned = str(int(token))
        else:
            cleaned = token.replace("*", "").replace("★", "").replace("star", "").replace("stars", "")
            cleaned = cleaned.strip()
        if not cleaned:
            return
        if cleaned not in seen_tiers:
            seen_tiers.add(cleaned)
            tiers.append(cleaned)

    for key in ("tags", "abilities", "immunities", "inflicts"):
        for value in raw.get(key) or []:
            add_filter(value)
    for value in raw.get("classes") or []:
        add_class(value)
    for value in raw.get("tiers") or raw.get("rarities") or []:
        add_tier(value)

    if catalog:
        for item in catalog:
            if isinstance(item, dict):
                if "value" in item:
                    add_filter(item.get("value"))
                    if item.get("type") == "class":
                        add_class(item.get("value"))
                    if item.get("type") == "tier":
                        add_tier(item.get("value"))
                else:
                    for key in ("label", "name", "value"):
                        if key in item:
                            add_filter(item.get(key))
                            break
            else:
                add_filter(item)

    return {"filters": filter_values, "classes": classes, "tiers": tiers}


async def start_champion_filter_flow(core: Any, ctx_or_interaction: Any, *, raw_input: Optional[str] = None, parsed_filters: Optional[Dict[str, Any]] = None, apply_pages_loader: Optional[Any] = None, result_title: str = "Champions", empty_message: str = "No champions match the selected filters.") -> bool:
    """Launch the champion filter selector with compact category buckets instead of one giant filter list.

    Discord Select widgets do not support text autocomplete; the practical workaround is to
    split filters into semantic groups and keep each list short enough for a user-facing picker.
    """
    if discord is None:
        return False

    if apply_pages_loader is None:
        apply_pages_loader = get_champion_pages

    catalog = _collect_champion_filter_catalog(core)
    sections = build_filter_picker_sections(catalog)
    state = build_filter_flow_state(parsed_filters or {}, catalog=catalog)
    author = getattr(ctx_or_interaction, "author", getattr(ctx_or_interaction, "user", ctx_or_interaction))
    if author is None:
        return False

    category_order = ["inflicts", "immune_to", "classes", "abilities", "tiers"]

    def _normalize_selected(values: Optional[List[Any]]) -> set:
        selected: set = set()
        for value in values or []:
            token = str(value or "").strip().lower().strip("#")
            if token:
                selected.add(token)
        return selected

    class _ChampionFilterSelect(discord.ui.Select):
        def __init__(self, *, key: str, placeholder: str, options: List[Any], page_values: List[str], max_values: int = 1, selected_values: Optional[set] = None):
            super().__init__(placeholder=placeholder, min_values=0, max_values=max_values, options=options)
            self.key = key
            self.page_values = list(page_values)
            self.selected_values = set(selected_values or set())

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, ChampionFilterSelectionView):
                return
            view.merge_page_selection(self.key, self.page_values, self.values)
            await view.refresh(interaction)

    class _ChampionFilterCategoryButton(discord.ui.Button):
        def __init__(self, *, category: str, selected_count: int):
            label = _filter_picker_category_label(category)
            if selected_count:
                label = f"{label} ({selected_count})"
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.category = category

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, ChampionFilterSelectionView):
                return
            view.active_category = self.category
            await view.refresh(interaction)

    class _ChampionFilterNavButton(discord.ui.Button):
        def __init__(self, *, label: str, step: int, disabled: bool = False):
            super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
            self.step = step

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, ChampionFilterSelectionView):
                return
            current = view.page_index.get(view.active_category, 0)
            page_values, total_pages = _filter_picker_page_values(view.section_values(view.active_category), current)
            del page_values
            view.page_index[view.active_category] = max(0, min(total_pages - 1, current + self.step))
            await view.refresh(interaction)

    class _ChampionFilterClearButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Clear Category", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, ChampionFilterSelectionView):
                return
            view.selected_by_category[view.active_category] = set()
            await view.refresh(interaction)

    class _ChampionFilterApplyButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Apply Filters", style=discord.ButtonStyle.success)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, ChampionFilterSelectionView):
                return
            await view.apply(interaction)

    class ChampionFilterSelectionView(discord.ui.View):
        def __init__(self, *, core: Any, author: Any, state: Dict[str, List[str]], raw_input: Optional[str] = None, parsed_filters: Optional[Dict[str, Any]] = None):
            super().__init__(timeout=180)
            self.core = core
            self.author = author
            self.state = dict(state)
            self.raw_input = raw_input or ""
            self.parsed_filters = dict(parsed_filters or {})
            self.sections = sections
            self.selected_by_category: Dict[str, set] = {
                "inflicts": _normalize_selected(self.parsed_filters.get("inflicts")),
                "immune_to": _normalize_selected(self.parsed_filters.get("immunities")),
                "classes": _normalize_selected(self.parsed_filters.get("classes")),
                "abilities": _normalize_selected(self.parsed_filters.get("abilities")),
                "tiers": _normalize_selected(self.parsed_filters.get("tiers") or self.parsed_filters.get("rarities")),
            }
            self.page_index: Dict[str, int] = {category: 0 for category in category_order}
            self.active_category = next((category for category in category_order if self.section_values(category)), "inflicts")
            self._rebuild_items()

        def section_values(self, category: str) -> List[str]:
            if category == "inflicts":
                return self.sections.get("inflicts", []) or ["bleed", "poison", "shock", "burn", "stun", "slow", "heal", "control"]
            if category == "immune_to":
                return self.sections.get("immune_to", []) or ["bleed", "poison", "shock", "slow", "stun", "control"]
            if category == "classes":
                return self.sections.get("classes", []) or ["skill", "mutant", "tech", "cosmic", "mystic", "science"]
            if category == "abilities":
                return self.sections.get("abilities", []) or ["incinerate", "shield", "healing", "buff", "debuff", "counter", "stun"]
            if category == "tiers":
                return self.sections.get("tiers", []) or ["6", "7"]
            return []

        def merge_page_selection(self, category: str, page_values: List[str], current_values: List[str]) -> None:
            selected = set(self.selected_by_category.get(category, set()))
            selected.difference_update(page_values)
            selected.update(str(value).strip().lower() for value in current_values if str(value).strip())
            self.selected_by_category[category] = selected

        def _build_select_options(self, category: str, page_values: List[str]) -> List[Any]:
            selected_values = self.selected_by_category.get(category, set())
            options: List[Any] = []
            for token in page_values:
                label = token.replace("-", " ").replace("_", " ").title()
                option = discord.SelectOption(label=label, value=token, default=token in selected_values)
                options.append(option)
            return options

        def _summary_lines(self) -> List[str]:
            lines: List[str] = []
            for category in category_order:
                selected = sorted(self.selected_by_category.get(category, set()))
                if selected:
                    lines.append(f"{_filter_picker_category_label(category)}: {', '.join(selected[:6])}{' ...' if len(selected) > 6 else ''}")
            return lines

        def build_embed(self) -> Any:
            current_values = self.section_values(self.active_category)
            current_page = self.page_index.get(self.active_category, 0)
            page_values, total_pages = _filter_picker_page_values(current_values, current_page)
            selected_count = len(self.selected_by_category.get(self.active_category, set()))
            summary = self._summary_lines()
            description_lines = [
                "Choose a category, then select values from that page.",
                f"Active category: {_filter_picker_category_label(self.active_category)}",
                f"Page {min(current_page + 1, total_pages)}/{total_pages} | Showing {len(page_values)} of {len(current_values)} values | Selected {selected_count}",
            ]
            if summary:
                description_lines.append("")
                description_lines.append("Current filters:")
                description_lines.extend(summary)
            return CDTEmbed.embed(self.author, title="Champion Filter Picker", description="\n".join(description_lines))

        def _rebuild_items(self) -> None:
            self.clear_items()
            for category in category_order:
                self.add_item(_ChampionFilterCategoryButton(category=category, selected_count=len(self.selected_by_category.get(category, set()))))

            current_values = self.section_values(self.active_category)
            current_page = self.page_index.get(self.active_category, 0)
            page_values, total_pages = _filter_picker_page_values(current_values, current_page)
            if page_values:
                options = self._build_select_options(self.active_category, page_values)
                max_values = min(25, len(options))
                self.add_item(_ChampionFilterSelect(key=self.active_category, placeholder=f"Select {_filter_picker_category_label(self.active_category)}", options=options, page_values=page_values, max_values=max_values, selected_values=self.selected_by_category.get(self.active_category, set())))

            self.add_item(_ChampionFilterNavButton(label="Prev", step=-1, disabled=current_page <= 0 or total_pages <= 1))
            self.add_item(_ChampionFilterNavButton(label="Next", step=1, disabled=current_page >= total_pages - 1 or total_pages <= 1))
            self.add_item(_ChampionFilterClearButton())
            self.add_item(_ChampionFilterApplyButton())

        async def refresh(self, interaction: Any) -> None:
            self._rebuild_items()
            embed = self.build_embed()
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                try:
                    await interaction.edit_original_response(embed=embed, view=self)
                except Exception:
                    pass

        async def apply(self, interaction: Any):
            final_filters = dict(self.parsed_filters)

            final_filters.pop("inflicts", None)
            final_filters.pop("immunities", None)
            final_filters.pop("classes", None)
            final_filters.pop("abilities", None)
            final_filters.pop("tiers", None)
            final_filters.pop("rarities", None)

            selected_inflicts = sorted(self.selected_by_category.get("inflicts", set()))
            selected_immune_to = sorted(self.selected_by_category.get("immune_to", set()))
            selected_classes = sorted(self.selected_by_category.get("classes", set()))
            selected_abilities = sorted(self.selected_by_category.get("abilities", set()))
            selected_tier_values = sorted(self.selected_by_category.get("tiers", set()))

            if selected_inflicts:
                final_filters["inflicts"] = selected_inflicts
            if selected_immune_to:
                final_filters["immunities"] = selected_immune_to
            if selected_classes:
                final_filters["classes"] = selected_classes
            if selected_abilities:
                final_filters["abilities"] = selected_abilities
            if selected_tier_values:
                final_filters["tiers"] = selected_tier_values
                final_filters["rarities"] = [int(v) for v in selected_tier_values if str(v).isdigit()]

            pages = await apply_pages_loader(self.core, interaction.user, final_filters)
            if not pages:
                try:
                    await interaction.response.edit_message(embed=CDTEmbed.embed(interaction.user, title=result_title, description=empty_message), view=None)
                except Exception:
                    await interaction.response.send_message(empty_message, ephemeral=True)
                return

            pager = CDTPagesMenu(pages, author=interaction.user)
            pager.filter_handler = lambda menu, btn_interaction: start_champion_filter_flow(self.core, btn_interaction, raw_input=self.raw_input, parsed_filters=final_filters, apply_pages_loader=apply_pages_loader, result_title=result_title, empty_message=empty_message)
            try:
                await interaction.response.edit_message(embed=pages[0], view=pager)
                pager.message = await interaction.original_response()
            except Exception:
                try:
                    await interaction.response.send_message(embed=pages[0], view=pager)
                    pager.message = await interaction.original_response()
                except Exception:
                    await interaction.followup.send(embed=pages[0], view=pager)

    embed = CDTEmbed.embed(author, title="Champion Filter Picker", description="Choose a category, then page through its full value list.\nDiscord select menus do not support live text autocomplete, so categories and pagination keep the picker usable.")
    view = ChampionFilterSelectionView(core=core, author=author, state=state, raw_input=raw_input, parsed_filters=parsed_filters)
    try:
        target_message = getattr(ctx_or_interaction, "message", None)
        if target_message is not None and hasattr(target_message, "edit"):
            await target_message.edit(embed=embed, view=view)
            return True
        response = getattr(ctx_or_interaction, "response", None)
        if response is not None and hasattr(response, "edit_message"):
            await response.edit_message(embed=embed, view=view)
            return True
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed, view=view)
            return True
        if hasattr(response, "send_message"):
            await response.send_message(embed=embed, view=view)
            return True
    except Exception:
        pass
    return False


def _normalized_tier_key(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Unranked"

    normalized = raw.strip().upper().replace("_", " ").replace("-", " ")
    if not normalized or "UNRANKED" in normalized:
        return "Unranked"

    match = re.search(r"(S\+|S|A|B|C|D|F)", normalized)
    if match:
        return match.group(1)

    # Some sources encode tiers like "C TIER", "Tier C", or "S+ Tier".
    compact = re.sub(r"[^A-Z0-9+]", "", normalized)
    for token in ["S+", "S", "A", "B", "C", "D", "F"]:
        if token in compact:
            return token

    return "Unranked"


def _tierlist_tier_order() -> List[str]:
    ordered = list(MCOCAPP_TIERS.keys())
    seen = set(ordered)
    for key in ["S+", "S", "A", "B", "C", "D", "F"]:
        if key not in seen:
            ordered.append(key)
    return ordered


def _tierlist_sort_key(champion: Dict[str, Any]) -> Tuple[int, float, str]:
    name = str(champion.get("name") or champion.get("slug") or "").strip().lower()
    tier_name = _normalized_tier_key(champion.get("tier") or "Unranked")
    tier_rank = _tierlist_tier_order().index(tier_name) if tier_name in _tierlist_tier_order() else len(_tierlist_tier_order())
    score = champion.get("score")
    try:
        score_value = float(score)
    except Exception:
        score_value = 0.0
    return (tier_rank, -score_value, name)


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

    canonical_order = list(tier_order or _tierlist_tier_order())
    ordered_groups: List[Dict[str, Any]] = []
    for tier in canonical_order:
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
            block.append(format_tierlist_champion_line(champ, long_labels=True))
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
    """Translate a tierlist page payload into Discord-safe embed objects.

    Discord caps an embed at 6000 chars, and a single tier group can still be larger than
    that when it contains dozens of champion lines. We split groups into subfields and
    flush pages before the embed exceeds a conservative maximum.
    """
    MAX_EMBED_CHARS = 5000
    MAX_FIELD_COUNT = 25
    TARGET_GROUP_CHARS = 900
    MAX_FIELD_VALUE_CHARS = 1024
    out: List[Any] = []

    def _make_embed(target_title: str, color: Any, field_batches: List[Tuple[str, str]], empty_message: str) -> Any:
        embed = CDTEmbed.embed(author, title=target_title, color=color, description="")
        for field_name, field_value in field_batches:
            if not field_value:
                continue
            CDTEmbed.add_field(author, embed, name=field_name, value=field_value, inline=False)
        if not getattr(embed, "fields", None):
            embed.description = empty_message
        return embed

    def _chunk_group_lines(group_title: str, lines: List[str]) -> List[Tuple[str, str]]:
        if not lines:
            return []
        chunks: List[Tuple[str, str]] = []
        current: List[str] = []
        current_size = 0
        chunk_index = 0

        for line in lines:
            line_size = len(line) + 1
            if current and (current_size + line_size > TARGET_GROUP_CHARS):
                value = "\n".join(current)
                if len(value) > 1024:
                    value = value[:1021] + "..."
                chunks.append((group_title if len(chunks) == 0 else f"{group_title} ({chunk_index + 1})", value))
                chunk_index += 1
                current = []
                current_size = 0
            current.append(line)
            current_size += line_size

        if current:
            value = "\n".join(current)
            if len(value) > 1024:
                value = value[:1021] + "..."
            chunks.append((group_title if len(chunks) == 0 else f"{group_title} ({chunk_index + 1})", value))

        return chunks

    for idx, page in enumerate(pages, start=1):
        page_groups = page.get("groups", []) or []
        if not page_groups:
            out.append(_make_embed(f"Tierlist ({idx}/{len(pages)})", page.get("color"), [], "No champions match your tierlist filters."))
            continue

        current_fields: List[Tuple[str, str]] = []
        current_size = 0
        current_title = f"Tierlist ({idx}/{len(pages)})"
        for group in page_groups:
            lines = [format_tierlist_champion_line(champion) for champion in (group.get("items", []) or [])]
            if not lines:
                continue
            for field_name, field_value in _chunk_group_lines(str(group.get("title", "Tier")), lines):
                proposal = (field_name, field_value)
                proposal_size = len(field_name) + len(field_value) + 32

                if current_fields and (
                    len(current_fields) >= MAX_FIELD_COUNT or
                    current_size + proposal_size > MAX_EMBED_CHARS
                ):
                    out.append(_make_embed(current_title, page.get("color"), current_fields, "No champions match your tierlist filters."))
                    current_fields = []
                    current_size = 0

                current_fields.append(proposal)
                current_size += proposal_size

        if current_fields:
            out.append(_make_embed(current_title, page.get("color"), current_fields, "No champions match your tierlist filters."))
        elif not out:
            out.append(_make_embed(current_title, page.get("color"), [], "No champions match your tierlist filters."))

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

        async def _handle_filter(menu: CDTPagesMenu, interaction: Any) -> None:
            try:
                await start_champion_filter_flow(core, interaction, raw_input=raw_input, parsed_filters=parsed)
            except Exception:
                try:
                    await interaction.response.send_message("Filter selection is unavailable right now.", ephemeral=True)
                except Exception:
                    pass

        try:
            pager.filter_handler = _handle_filter
        except Exception:
            pass

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
