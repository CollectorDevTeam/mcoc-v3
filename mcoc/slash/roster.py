# Path: mcoc/slash/roster.py
# File-Version: 1.0
# File-Id: 4dcbf22d-1995-4760-aa55-406751721366
# Purpose: Provide slash command handler for MCOC roster management commands.
# Public-API: _RosterGroup
# Last-Modified: 2026-09-01
# Used-By: mcoc/common/components/componentsV2.py, mcoc/common/helpers/roster.py, mcoc/common/utilities/hargs.py
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header


import logging
import re
from typing import Optional, Any, List, Tuple
import discord
from discord import Attachment, ui
from redbot.core import commands
from redbot.core import app_commands

log = logging.getLogger("red.mcoc.slash.roster")

from ..common.utilities.hargs import parse_hargs
from ..common.helpers.roster import (
    ensure_user_manager,
    extract_entry_from_parsed,
    build_roster_pages,
    make_roster_pager,
    parse_roster_entries_from_input,
    parse_roster_entries_with_errors,
    import_roster_entries,
    validate_entry_for_add,
)
from ..common.helpers.types import CLASS_EMOJI
from ..common.components.componentsV2 import CDTEmbed, CDTPagesMenu, CDTConfirm


ROSTER_CLASSES = {"science", "skill", "mutant", "tech", "cosmic", "mystic"}
TIER_DISPLAY_ORDER = ["S+", "S", "A", "B", "C", "D", "E", "F"]


class _RosterAddModal(ui.Modal):
    def __init__(
        self,
        core: Any,
        champion: str,
        *,
        remaining: Optional[List[str]] = None,
        added_lines: Optional[List[str]] = None,
        failed_lines: Optional[List[str]] = None,
    ):
        self.core = core
        self.champion = champion.strip()
        self.remaining = list(remaining or [])
        self.added_lines = list(added_lines or [])
        self.failed_lines = list(failed_lines or [])

        modal_title = f"Add {self.champion}" if self.champion else "Add roster entry"
        super().__init__(title=modal_title[:45])
        self.rarity = ui.TextInput(label="Rarity (stars)", placeholder="7", default="7")
        self.rank = ui.TextInput(label="Rank", placeholder="1", default="1")
        self.sig = ui.TextInput(label="Signature (0-200)", placeholder="0", default="0", required=False)
        self.ascended = ui.TextInput(label="Ascended? (0 or 1)", placeholder="0", default="0", required=False)
        self.add_item(self.rarity)
        self.add_item(self.rank)
        self.add_item(self.sig)
        self.add_item(self.ascended)

    async def on_submit(self, interaction):
        try:
            rarity = int((self.rarity.value or "7").strip() or 7)
            rank = int((self.rank.value or "1").strip() or 1)
            sig = int((self.sig.value or "0").strip() or 0)
            ascended = int((self.ascended.value or "0").strip() or 0)
        except ValueError:
            await interaction.response.send_message("Please enter valid numeric values for rarity, rank, signature, and ascended.", ephemeral=True)
            return

        raw_input = f"{self.champion} {rarity}*r{rank} s{sig} a{ascended}"
        try:
            entries, _failed = parse_roster_entries_with_errors(raw_input, getattr(self.core, "cache", None))
        except Exception:
            entries = []

        if not entries:
            self.failed_lines.append(self.champion)
            if self.remaining:
                next_champion = self.remaining[0]
                await interaction.response.send_modal(
                    _RosterAddModal(
                        self.core,
                        next_champion,
                        remaining=self.remaining[1:],
                        added_lines=self.added_lines,
                        failed_lines=self.failed_lines,
                    )
                )
                return
            await interaction.response.send_message(
                f"Could not resolve `{self.champion}` for roster add.",
                ephemeral=True,
            )
            return

        users = ensure_user_manager(self.core)
        cache = getattr(self.core, "cache", None)
        added_now = 0
        for entry in entries:
            try:
                users.add_champion(
                    interaction.user.id,
                    entry["champion"],
                    int(entry["rarity"]),
                    int(entry["rank"]),
                    int(entry.get("sig", 0)),
                    int(entry.get("ascended", 0)),
                    tags=entry.get("tags", []),
                )
                added_now += 1
                champ = cache.get_champion(entry["champion"]) if cache else None
                name = champ.get("name") if isinstance(champ, dict) else entry["champion"]
                self.added_lines.append(
                    f"{name} {entry['rarity']}* r{entry['rank']} s{entry.get('sig', 0)} a{entry.get('ascended', 0)}"
                )
            except Exception:
                log.exception("Failed to add modal roster entry %s", entry)
                self.failed_lines.append(self.champion)

        if self.remaining:
            next_champion = self.remaining[0]
            await interaction.response.send_modal(
                _RosterAddModal(
                    self.core,
                    next_champion,
                    remaining=self.remaining[1:],
                    added_lines=self.added_lines,
                    failed_lines=self.failed_lines,
                )
            )
            return

        if self.added_lines:
            lines = "\n".join(self.added_lines[:20])
            message = f"Added {len(self.added_lines)} champion(s) to your roster."
            if lines:
                message += f"\n{lines}"
            if self.failed_lines:
                message += "\n\nCould not resolve: " + ", ".join(self.failed_lines[:10])
            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("No roster entries were added.", ephemeral=True)


class _RosterListControlsView(ui.View):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str = "", parsed_filters: Optional[dict] = None, *, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.group = group
        self.target_user = target_user
        self.base_hargs = base_hargs or ""
        self.parsed_filters = dict(parsed_filters or {})
        for label, mode in (("AWAKEN", "awaken"), ("RANKUP", "rankup"), ("TIERLIST", "tierlist"), ("CLEAR", "default")):
            self.add_item(_RosterListModeButton(group, target_user, self.base_hargs, label, mode, parsed_filters=self.parsed_filters))


class _RosterQuickFilterSelect(ui.Select):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str, parsed_filters: dict, kind: str, anchor_message: Any):
        self.group = group
        self.target_user = target_user
        self.base_hargs = base_hargs or ""
        self.parsed_filters = dict(parsed_filters or {})
        self.kind = kind
        self.anchor_message = anchor_message

        if kind == "star":
            options = [
                discord.SelectOption(label="Any Star", value=""),
                discord.SelectOption(label="7★", value="7"),
                discord.SelectOption(label="6★", value="6"),
                discord.SelectOption(label="5★", value="5"),
                discord.SelectOption(label="4★", value="4"),
            ]
            placeholder = "Select star tier"
        elif kind == "rank":
            options = [
                discord.SelectOption(label="Any Rank", value=""),
                discord.SelectOption(label="Rank 1", value="1"),
                discord.SelectOption(label="Rank 2", value="2"),
                discord.SelectOption(label="Rank 3", value="3"),
                discord.SelectOption(label="Rank 4", value="4"),
                discord.SelectOption(label="Rank 5", value="5"),
            ]
            placeholder = "Select rank"
        else:
            options = [
                discord.SelectOption(label="All Classes", value=""),
                discord.SelectOption(label="Science", value="science"),
                discord.SelectOption(label="Skill", value="skill"),
                discord.SelectOption(label="Mutant", value="mutant"),
                discord.SelectOption(label="Tech", value="tech"),
                discord.SelectOption(label="Cosmic", value="cosmic"),
                discord.SelectOption(label="Mystic", value="mystic"),
            ]
            placeholder = "Select class"

        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction):
        parsed = dict(self.parsed_filters or {})
        selected = str((self.values or [""])[0] or "").strip().lower()
        if self.kind == "star":
            if selected and selected.isdigit():
                parsed["rarities"] = [int(selected)]
            else:
                parsed.pop("rarities", None)
        elif self.kind == "rank":
            if selected and selected.isdigit():
                parsed["ranks"] = [int(selected)]
            else:
                parsed.pop("ranks", None)
        else:
            if selected:
                parsed["classes"] = [selected]
            else:
                parsed.pop("classes", None)

        try:
            pager = await self.group._build_roster_list_pager(self.target_user, self.base_hargs, parsed, author_for_controls=getattr(interaction, "user", self.target_user))
            if not pager:
                await interaction.response.send_message("No roster entries match the selected filters.", ephemeral=True)
                return
            embed = pager.pages[0]
            if self.anchor_message is not None and hasattr(self.anchor_message, "edit"):
                await self.anchor_message.edit(embed=embed, view=pager)
            await interaction.response.edit_message(content="Applied.", view=None)
        except Exception:
            log.exception("roster quick filter apply failed")
            await interaction.response.send_message("Unable to apply filter right now.", ephemeral=True)


class _RosterQuickFilterPickerView(ui.View):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str, parsed_filters: dict, kind: str, anchor_message: Any):
        super().__init__(timeout=120)
        self.add_item(_RosterQuickFilterSelect(group, target_user, base_hargs, parsed_filters, kind, anchor_message))


class _RosterFilterCategoryButton(ui.Button):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str, parsed_filters: dict, label: str, kind: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.group = group
        self.target_user = target_user
        self.base_hargs = base_hargs or ""
        self.parsed_filters = dict(parsed_filters or {})
        self.kind = kind

    async def callback(self, interaction):
        try:
            picker = _RosterQuickFilterPickerView(
                self.group,
                self.target_user,
                self.base_hargs,
                self.parsed_filters,
                self.kind,
                getattr(interaction, "message", None),
            )
            await interaction.response.send_message("Choose a value:", view=picker, ephemeral=True)
        except Exception:
            log.exception("roster filter category button failed")
            await interaction.response.send_message("Unable to open filter picker right now.", ephemeral=True)


class _RosterFilterCategoryView(ui.View):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str, parsed_filters: dict):
        super().__init__(timeout=120)
        self.add_item(_RosterFilterCategoryButton(group, target_user, base_hargs, parsed_filters, "STAR", "star"))
        self.add_item(_RosterFilterCategoryButton(group, target_user, base_hargs, parsed_filters, "RANK", "rank"))
        self.add_item(_RosterFilterCategoryButton(group, target_user, base_hargs, parsed_filters, "CLASS", "class"))


class _RosterListModeButton(ui.Button):
    def __init__(self, group: "_RosterGroup", target_user: Any, base_hargs: str, label: str, mode: str, *, parsed_filters: Optional[dict] = None):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.group = group
        self.target_user = target_user
        self.base_hargs = base_hargs or ""
        self.parsed_filters = dict(parsed_filters or {})
        self.mode = mode or "default"

    async def callback(self, interaction):
        try:
            parsed = dict(self.parsed_filters or parse_hargs(self.base_hargs or ""))
            if self.mode == "default":
                parsed.pop("list_mode", None)
            else:
                parsed["list_mode"] = self.mode
            pager = await self.group._build_roster_list_pager(
                self.target_user,
                self.base_hargs,
                parsed,
                author_for_controls=getattr(interaction, "user", self.target_user),
            )
            if not pager:
                await interaction.response.send_message("No roster entries match the selected view.", ephemeral=True)
                return
            embed = pager.pages[0]
            try:
                if hasattr(interaction.response, "edit_message"):
                    await interaction.response.edit_message(embed=embed, view=pager)
                    return
                if getattr(interaction, "message", None) is not None and hasattr(interaction.message, "edit"):
                    await interaction.message.edit(embed=embed, view=pager)
                    return
                await interaction.response.send_message(embed=embed, view=pager)
            except Exception:
                await interaction.response.send_message(embed=embed)
        except Exception:
            log.exception("roster list mode callback failed")
            await interaction.response.send_message("Roster list is unavailable right now.", ephemeral=True)


class _RosterGroup(app_commands.Group):
    def __init__(self, core: Any):
        super().__init__(name="roster", description="Manage your personal champion roster")
        self.core = core
        self._init_failed = False
        # do not create heavy objects here

    async def _build_roster_list_pager(self, target_user: Any, base_hargs: str, parsed_filters: dict, *, author_for_controls: Any) -> Optional[CDTPagesMenu]:
        pager = await make_roster_pager(
            self.core,
            target_user,
            raw_input=base_hargs or "",
            parsed_filters=parsed_filters,
            author_for_controls=author_for_controls,
        )
        if not pager:
            return None
        try:
            # Preserve roster list controls when switching to paged views.
            controls = _RosterListControlsView(self, target_user, base_hargs or "", parsed_filters=parsed_filters)
            for item in getattr(controls, "children", []) or []:
                pager.add_item(item)
        except Exception:
            pass
        async def _open_filter_categories(_menu: CDTPagesMenu, interaction: Any) -> None:
            view = _RosterFilterCategoryView(self, target_user, base_hargs or "", parsed_filters)
            await interaction.response.send_message("Filter picker:", view=view, ephemeral=True)

        try:
            pager.filter_handler = _open_filter_categories
        except Exception:
            pass
        return pager

    async def _prompt_single_champion_modal(self, interaction, champion: str):
        await interaction.response.send_modal(_RosterAddModal(self.core, champion))

    async def _prompt_modal_queue(self, interaction, champions: List[str]):
        queue = [c.strip() for c in champions if c and c.strip()]
        if not queue:
            await interaction.response.send_message("No champions were provided.", ephemeral=True)
            return
        await interaction.response.send_modal(_RosterAddModal(self.core, queue[0], remaining=queue[1:]))

    def _split_champion_candidates(self, raw: str) -> List[str]:
        return [token.strip() for token in re.split(r"[,;\n]+", raw or "") if token and token.strip()]

    def _champion_rows(self) -> List[Tuple[str, str]]:
        champs = getattr(self.core, "cache", None) and self.core.cache.get_all_champions() or []
        rows: List[Tuple[str, str]] = []
        for champ in champs:
            name = str(champ.get("name") or "").strip()
            cid = str(champ.get("id") or champ.get("slug") or "").strip()
            if name and cid:
                rows.append((name, cid))
        return rows

    def _resolve_entry_class(self, cache: Any, champ_slug: str) -> str:
        try:
            champ = cache.get_champion(champ_slug) if cache else None
        except Exception:
            champ = None
        champ_class = str((champ or {}).get("class") or (champ or {}).get("class_name") or "").strip().lower()
        return champ_class if champ_class in ROSTER_CLASSES else "unknown"

    def _apply_per_class_target(
        self,
        candidates: List[dict],
        class_counts: dict,
        per_class_target: int,
        class_filter: str,
    ) -> List[dict]:
        if per_class_target <= 0:
            return candidates

        if class_filter != "all":
            return candidates[:per_class_target]

        selected: List[dict] = []
        grouped = {k: [] for k in ROSTER_CLASSES}
        for row in candidates:
            row_class = str(row.get("class") or "").lower()
            if row_class in grouped:
                grouped[row_class].append(row)

        class_order = ["science", "skill", "mutant", "tech", "cosmic", "mystic"]
        for cls in class_order:
            have = int(class_counts.get(cls, 0) or 0)
            need = max(0, int(per_class_target) - have)
            if need <= 0:
                continue
            selected.extend(grouped.get(cls, [])[:need])

        return selected

    def _tierlist_score_map(self) -> dict:
        def _canonical_tokens(value: Any) -> List[str]:
            base = str(value or "").strip().lower()
            if not base:
                return []
            compact = re.sub(r"[^a-z0-9]+", "", base)
            dashed = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
            undashed = dashed.replace("-", "") if dashed else ""
            out = [base]
            for token in (compact, dashed, undashed):
                if token and token not in out:
                    out.append(token)
            return out

        cache = getattr(self.core, "cache", None)
        if not cache or not hasattr(cache, "_load_file"):
            return {}
        try:
            tierlist = cache._load_file("tierlist") or {}
        except Exception:
            return {}
        champions = tierlist.get("champions") if isinstance(tierlist, dict) else []
        if not isinstance(champions, list):
            return {}

        scores = {}
        for row in champions:
            if not isinstance(row, dict):
                continue
            try:
                score = float(row.get("score", 0) or 0)
            except Exception:
                score = 0.0
            for key in (row.get("id"), row.get("slug"), row.get("name"), row.get("en")):
                for token in _canonical_tokens(key):
                    if token not in scores:
                        scores[token] = score
        return scores

    def _tierlist_tier_map(self) -> dict:
        def _canonical_tokens(value: Any) -> List[str]:
            base = str(value or "").strip().lower()
            if not base:
                return []
            compact = re.sub(r"[^a-z0-9]+", "", base)
            dashed = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
            undashed = dashed.replace("-", "") if dashed else ""
            out = [base]
            for token in (compact, dashed, undashed):
                if token and token not in out:
                    out.append(token)
            return out

        cache = getattr(self.core, "cache", None)
        if not cache or not hasattr(cache, "_load_file"):
            return {}
        try:
            tierlist = cache._load_file("tierlist") or {}
        except Exception:
            return {}
        champions = tierlist.get("champions") if isinstance(tierlist, dict) else []
        if not isinstance(champions, list):
            return {}

        tiers = {}
        for row in champions:
            if not isinstance(row, dict):
                continue
            tier = str(row.get("tier") or "").strip().upper()
            if not tier:
                continue
            for key in (row.get("id"), row.get("slug"), row.get("name"), row.get("en")):
                for token in _canonical_tokens(key):
                    if token not in tiers:
                        tiers[token] = tier
        return tiers

    def _tierlist_awakened_set(self) -> set:
        def _canonical_tokens(value: Any) -> List[str]:
            base = str(value or "").strip().lower()
            if not base:
                return []
            compact = re.sub(r"[^a-z0-9]+", "", base)
            dashed = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
            undashed = dashed.replace("-", "") if dashed else ""
            out = [base]
            for token in (compact, dashed, undashed):
                if token and token not in out:
                    out.append(token)
            return out

        cache = getattr(self.core, "cache", None)
        if not cache or not hasattr(cache, "_load_file"):
            return set()
        try:
            tierlist = cache._load_file("tierlist") or {}
        except Exception:
            return set()
        champions = tierlist.get("champions") if isinstance(tierlist, dict) else []
        if not isinstance(champions, list):
            return set()

        awakened_needed = set()
        for row in champions:
            if not isinstance(row, dict):
                continue
            if not bool(row.get("awakened", False)):
                continue
            for key in (row.get("id"), row.get("slug"), row.get("name"), row.get("en")):
                for token in _canonical_tokens(key):
                    awakened_needed.add(token)
        return awakened_needed

    def _rankup_suggestions(
        self,
        user_id: int,
        class_filter: Optional[str],
        stars: int,
        target_rank: int,
        per_class_target: int = 0,
    ) -> List[dict]:
        users = ensure_user_manager(self.core)
        if not users or not hasattr(users, "list_roster"):
            return []
        try:
            roster_entries = users.list_roster(user_id) or []
        except Exception:
            roster_entries = []

        cache = getattr(self.core, "cache", None)
        score_map = self._tierlist_score_map()
        tier_map = self._tierlist_tier_map()
        out = []
        class_counts = {k: 0 for k in ROSTER_CLASSES}

        for entry in roster_entries:
            try:
                slug = str(entry.get("champion") or "").strip().lower()
                rarity = int(entry.get("rarity") or entry.get("stars") or 0)
                rank = int(entry.get("rank") or 0)
                if rarity != int(stars):
                    continue

                champ_class = self._resolve_entry_class(cache, slug)
                if rank >= int(target_rank) and champ_class in class_counts:
                    class_counts[champ_class] += 1
                if rank >= int(target_rank):
                    continue

                champ = cache.get_champion(slug) if cache else None
                if class_filter and class_filter != "all" and champ_class != class_filter:
                    continue

                name = str((champ or {}).get("name") or slug).strip() or slug
                keys = [slug, name.lower()]
                keys.append(re.sub(r"[^a-z0-9]+", "", slug.lower()))
                keys.append(re.sub(r"[^a-z0-9]+", "", name.lower()))
                score = 0.0
                for key in keys:
                    if key in score_map:
                        score = float(score_map[key])
                        break

                tier = ""
                for key in keys:
                    if key in tier_map:
                        tier = str(tier_map[key])
                        break

                out.append(
                    {
                        "slug": slug,
                        "name": name,
                        "class": champ_class or "unknown",
                        "rarity": rarity,
                        "rank": rank,
                        "target_rank": int(target_rank),
                        "score": score,
                        "tier": tier,
                    }
                )
            except Exception:
                continue

        out.sort(key=lambda e: (-float(e.get("score", 0.0)), str(e.get("name") or "").lower()))
        return self._apply_per_class_target(out, class_counts, int(per_class_target or 0), class_filter or "all")

    def _awaken_suggestions(
        self,
        user_id: int,
        class_filter: Optional[str],
        stars: int,
        min_rank: int,
        per_class_target: int = 0,
    ) -> List[dict]:
        users = ensure_user_manager(self.core)
        if not users or not hasattr(users, "list_roster"):
            return []
        try:
            roster_entries = users.list_roster(user_id) or []
        except Exception:
            roster_entries = []

        cache = getattr(self.core, "cache", None)
        score_map = self._tierlist_score_map()
        tier_map = self._tierlist_tier_map()
        awakened_needed = self._tierlist_awakened_set()
        out = []
        class_counts = {k: 0 for k in ROSTER_CLASSES}

        for entry in roster_entries:
            try:
                slug = str(entry.get("champion") or "").strip().lower()
                rarity = int(entry.get("rarity") or entry.get("stars") or 0)
                rank = int(entry.get("rank") or 0)
                sig = int(entry.get("sig") or 0)
                if rarity != int(stars):
                    continue
                champ_class = self._resolve_entry_class(cache, slug)
                if rank >= int(min_rank) and sig > 0 and champ_class in class_counts:
                    class_counts[champ_class] += 1
                if rank < int(min_rank):
                    continue
                if sig > 0:
                    # Already awakened/sigged; first pass only suggests non-awakened entries.
                    continue

                champ = cache.get_champion(slug) if cache else None
                if class_filter and class_filter != "all" and champ_class != class_filter:
                    continue

                name = str((champ or {}).get("name") or slug).strip() or slug
                keys = [slug, name.lower()]
                keys.append(re.sub(r"[^a-z0-9]+", "", slug.lower()))
                keys.append(re.sub(r"[^a-z0-9]+", "", name.lower()))
                tierlist_match = any(token in awakened_needed for token in keys)
                if not tierlist_match:
                    continue

                score = 0.0
                for key in keys:
                    if key in score_map:
                        score = float(score_map[key])
                        break

                tier = ""
                for key in keys:
                    if key in tier_map:
                        tier = str(tier_map[key])
                        break

                out.append(
                    {
                        "slug": slug,
                        "name": name,
                        "class": champ_class or "unknown",
                        "rarity": rarity,
                        "rank": rank,
                        "score": score,
                        "tier": tier,
                    }
                )
            except Exception:
                continue

        out.sort(key=lambda e: (-float(e.get("score", 0.0)), str(e.get("name") or "").lower()))
        return self._apply_per_class_target(out, class_counts, int(per_class_target or 0), class_filter or "all")

    def _build_rankup_pages(self, interaction, class_filter: str, stars: int, target_rank: int, suggestions: List[dict], per_class_target: int = 0) -> List[Any]:
        label = "All" if class_filter == "all" else class_filter.title()
        title = f"Roster Rankup Suggestions: {label} {stars}★ -> r{target_rank}"
        if per_class_target > 0:
            title = f"{title} | target/class: {per_class_target}"
        if not suggestions:
            return [CDTEmbed.embed(interaction, title=title, description="No eligible champions found for these filters.")]

        grouped_fields = []
        seen_tiers = set()
        for tier in TIER_DISPLAY_ORDER:
            tier_rows = [row for row in suggestions if str(row.get("tier") or "").upper() == tier]
            if not tier_rows:
                continue
            seen_tiers.add(tier)
            value = "\n".join(
                f"{(CLASS_EMOJI.get(str(row.get('class') or '').lower()) or CLASS_EMOJI.get('all') or '')} {row['name']} ({str(row.get('class') or 'unknown').title()}) {row['rarity']}★ r{row['rank']} -> r{row['target_rank']} | score {row['score']:.1f}"
                for row in tier_rows
            )
            grouped_fields.append((f"{tier} TIER", value))

        other_rows = [row for row in suggestions if str(row.get("tier") or "").upper() not in seen_tiers]
        if other_rows:
            grouped_fields.append(("OTHER TIER", "\n".join(
                f"{(CLASS_EMOJI.get(str(row.get('class') or '').lower()) or CLASS_EMOJI.get('all') or '')} {row['name']} ({str(row.get('class') or 'unknown').title()}) {row['rarity']}★ r{row['rank']} -> r{row['target_rank']} | score {row['score']:.1f}"
                for row in other_rows
            )))

        page_chunks = []
        chunk = []
        for field_name, value in grouped_fields:
            if len(chunk) >= 5:
                page_chunks.append(chunk)
                chunk = []
            chunk.append((field_name, value))
        if chunk:
            page_chunks.append(chunk)

        pages = []
        total = len(page_chunks)
        for i, chunk_fields in enumerate(page_chunks, start=1):
            emb = CDTEmbed.embed(interaction, title=title, footer_text=f"Page {i} of {total}")
            for field_name, value in chunk_fields:
                CDTEmbed.add_field(interaction, emb, name=field_name, value=value, inline=False)
            pages.append(emb)
        return pages

    def _build_awaken_pages(self, interaction, class_filter: str, stars: int, min_rank: int, suggestions: List[dict], per_class_target: int = 0) -> List[Any]:
        label = "All" if class_filter == "all" else class_filter.title()
        title = f"Roster Awaken Suggestions: {label} {stars}★ (r{min_rank}+ )"
        if per_class_target > 0:
            title = f"{title} | target/class: {per_class_target}"
        if not suggestions:
            return [CDTEmbed.embed(interaction, title=title, description="No eligible champions found for these filters.")]

        grouped_fields = []
        seen_tiers = set()
        for tier in TIER_DISPLAY_ORDER:
            tier_rows = [row for row in suggestions if str(row.get("tier") or "").upper() == tier]
            if not tier_rows:
                continue
            seen_tiers.add(tier)
            value = "\n".join(
                f"{(CLASS_EMOJI.get(str(row.get('class') or '').lower()) or CLASS_EMOJI.get('all') or '')} {row['name']} ({str(row.get('class') or 'unknown').title()}) {row['rarity']}★ r{row['rank']} s0 | score {row['score']:.1f}"
                for row in tier_rows
            )
            grouped_fields.append((f"{tier} TIER", value))

        other_rows = [row for row in suggestions if str(row.get("tier") or "").upper() not in seen_tiers]
        if other_rows:
            grouped_fields.append(("OTHER TIER", "\n".join(
                f"{(CLASS_EMOJI.get(str(row.get('class') or '').lower()) or CLASS_EMOJI.get('all') or '')} {row['name']} ({str(row.get('class') or 'unknown').title()}) {row['rarity']}★ r{row['rank']} s0 | score {row['score']:.1f}"
                for row in other_rows
            )))

        page_chunks = []
        chunk = []
        for field_name, value in grouped_fields:
            if len(chunk) >= 5:
                page_chunks.append(chunk)
                chunk = []
            chunk.append((field_name, value))
        if chunk:
            page_chunks.append(chunk)

        pages = []
        total = len(page_chunks)
        for i, chunk_fields in enumerate(page_chunks, start=1):
            emb = CDTEmbed.embed(interaction, title=title, footer_text=f"Page {i} of {total}")
            for field_name, value in chunk_fields:
                CDTEmbed.add_field(interaction, emb, name=field_name, value=value, inline=False)
            pages.append(emb)
        return pages

    async def _add_entries(self, interaction, raw_input: str):
        cache = getattr(self.core, "cache", None)
        try:
            entries, failed = parse_roster_entries_with_errors(raw_input, cache)
        except Exception:
            entries, failed = [], []

        if not entries:
            return False

        users = ensure_user_manager(self.core)
        added = 0
        added_lines = []
        for entry in entries:
            try:
                users.add_champion(
                    interaction.user.id,
                    entry["champion"],
                    int(entry["rarity"]),
                    int(entry["rank"]),
                    int(entry.get("sig", 0)),
                    int(entry.get("ascended", 0)),
                    tags=entry.get("tags", []),
                )
                added += 1
                champ = cache.get_champion(entry["champion"]) if cache else None
                name = champ.get("name") if isinstance(champ, dict) else entry["champion"]
                added_lines.append(f"{name} {entry['rarity']}* r{entry['rank']} s{entry.get('sig', 0)}")
            except Exception:
                log.exception("Failed to add roster entry %s", entry)

        if added:
            message = f"Added {added} champion(s) to your roster."
            if added_lines:
                message += "\n" + "\n".join(added_lines[:20])
            if failed:
                message += "\n\nCould not resolve: " + ", ".join(failed[:10])
            await interaction.response.send_message(message)
            return True
        return False

    # Autocomplete: champion names (prefer index)
    async def champion_autocomplete(self, interaction, current: str):
        raw = str(current or "")
        delim_pos = max(raw.rfind(","), raw.rfind(";"), raw.rfind("\n"))

        if delim_pos >= 0:
            prefix = raw[: delim_pos + 1]
            token = raw[delim_pos + 1 :].lstrip()
            cur = token.lower()
            if prefix and not prefix.endswith(" "):
                prefix = f"{prefix} "

            matches = []
            for name, cid in self._champion_rows():
                if cur in name.lower() or cur in cid.lower():
                    value = f"{prefix}{name}, "
                    if len(value) > 100:
                        value = f"{prefix}{cid}, "
                    if len(value) <= 100:
                        matches.append(app_commands.Choice(name=name, value=value))
                    if len(matches) >= 25:
                        break
            return matches

        idx = getattr(self.core, "cache", None) and getattr(self.core.cache, "index", None)
        cur = raw.lower()
        if idx and hasattr(idx, "champion_autocomplete"):
            try:
                return await idx.champion_autocomplete(interaction, cur)
            except Exception:
                log.exception("champion_autocomplete failed in CacheIndex")
        # fallback simple scan
        try:
            matches = []
            for name, cid in self._champion_rows():
                if cur in name.lower() or cur in cid.lower():
                    matches.append(app_commands.Choice(name=name, value=cid))
                    if len(matches) >= 25:
                        break
            return matches
        except Exception:
            return []

    # Autocomplete: hargs presets
    async def hargs_autocomplete(self, interaction, current: str):
        cur = (current or "").lower()
        presets = [
            "7*", "7*r1", "7*r2", "7*r3", "7*r4", "7*r5",
            "6*", "6*r1", "6*r2", "6*r3", "6*r4", "6*r5",
            "5*", "5*r1", "5*r2", "5*r3", "5*r4", "5*r5",
            "r1", "r2", "r3", "r4", "r5",
            "s0", "s20", "s40", "s80", "s120", "s200",
            "#bleed", "#poison", "#shock", "#incinerate",
        ]
        return [app_commands.Choice(name=p, value=p) for p in presets if cur in p.lower()][:25]

    async def _run_rankup_suggestions(self, interaction, class_filter: str, stars: int, target_rank: int, per_class_target: int = 0):
        suggestions = self._rankup_suggestions(interaction.user.id, class_filter, stars, target_rank, per_class_target)
        pages = self._build_rankup_pages(interaction, class_filter, stars, target_rank, suggestions, per_class_target)
        if not pages:
            await interaction.response.send_message("No rankup suggestions are available.", ephemeral=True)
            return
        try:
            menu = CDTPagesMenu(pages, author=interaction.user)
            await interaction.response.send_message(embed=pages[0], view=menu)
        except Exception:
            await interaction.response.send_message(embed=pages[0])

    async def _run_awaken_suggestions(self, interaction, class_filter: str, stars: int, min_rank: int, per_class_target: int = 0):
        suggestions = self._awaken_suggestions(interaction.user.id, class_filter, stars, min_rank, per_class_target)
        pages = self._build_awaken_pages(interaction, class_filter, stars, min_rank, suggestions, per_class_target)
        if not pages:
            await interaction.response.send_message("No awaken suggestions are available.", ephemeral=True)
            return
        try:
            menu = CDTPagesMenu(pages, author=interaction.user)
            await interaction.response.send_message(embed=pages[0], view=menu)
        except Exception:
            await interaction.response.send_message(embed=pages[0])

    async def _resolve_target_for_list(self, interaction, raw_hargs: str):
        text = str(raw_hargs or "").strip()
        if not text:
            return interaction.user, text

        mention_match = re.search(r"<@!?(\d+)>", text)
        if not mention_match:
            return interaction.user, text

        user_id = int(mention_match.group(1))
        cleaned = (text[: mention_match.start()] + " " + text[mention_match.end() :]).strip()

        guild = getattr(interaction, "guild", None)
        if guild and hasattr(guild, "get_member"):
            member = guild.get_member(user_id)
            if member is not None:
                return member, cleaned

        client = getattr(interaction, "client", None)
        if client and hasattr(client, "get_user"):
            cached = client.get_user(user_id)
            if cached is not None:
                return cached, cleaned
        if client and hasattr(client, "fetch_user"):
            try:
                fetched = await client.fetch_user(user_id)
                if fetched is not None:
                    return fetched, cleaned
            except Exception:
                pass

        return interaction.user, cleaned

    # -------------------------
    # /roster add
    # -------------------------
    @app_commands.command(name="add", description="Add a champion to your roster")
    @app_commands.autocomplete(champion=champion_autocomplete, hargs=hargs_autocomplete)
    async def add(self, interaction, champion: str, hargs: Optional[str] = None):
        cache = getattr(self.core, "cache", None)
        champion_text = str(champion or "").strip()
        hargs_text = str(hargs or "").strip()
        raw_input = " ".join(part for part in (champion_text, hargs_text) if part).strip()

        has_harg_markers = bool(re.search(r"(?:\d\s*(?:\*|★)|\br\d+\b|\bs\d{1,4}\b|\ba\d+\b)", champion_text, flags=re.IGNORECASE))
        if hargs_text or has_harg_markers:
            try:
                entries, failed = parse_roster_entries_with_errors(raw_input, cache)
            except Exception:
                entries, failed = [], []
            if entries:
                await self._add_entries(interaction, raw_input)
                return

        if not hargs_text:
            candidates = self._split_champion_candidates(champion_text)
            if len(candidates) > 1:
                await self._prompt_modal_queue(interaction, candidates)
                return
            # Bare champion names should open the modal instead of silently defaulting to rank 1 / rarity 7.
            await self._prompt_single_champion_modal(interaction, champion_text)
            return

        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        champ = None
        if cache:
            try:
                champ = cache.get_champion(champion)
            except Exception:
                champ = None

        if not champ:
            await interaction.response.send_message(f"Champion `{champion}` not found.", ephemeral=True)
            return

        if not validate_entry_for_add(entry):
            await interaction.response.send_message("Adding a champion requires rarity and rank (e.g., `6*r3`).", ephemeral=True)
            return

        users = ensure_user_manager(self.core)
        try:
            users.add_champion(
                interaction.user.id,
                champ_slug=champ.get("id") or champ.get("slug"),
                rarity=entry["rarity"],
                rank=entry["rank"],
                sig=entry.get("sig", 0),
                tags=entry.get("tags", []),
            )
        except Exception:
            log.exception("Failed to add champion to roster")
            await interaction.response.send_message("Failed to add champion to roster.", ephemeral=True)
            return

        try:
            embed = await CDTEmbed.roster_entry_embed(interaction, champ, {
                "rarity": entry["rarity"],
                "rank": entry["rank"],
                "sig": entry.get("sig", 0),
                "tags": entry.get("tags", []),
                "ascended": entry.get("ascended", 0),
            })
        except Exception:
            embed = None

        await interaction.response.send_message(f"Added **{champ.get('name','Unknown')}** to your roster.", embed=embed)

    @app_commands.command(name="rankup", description="Suggest rankup candidates from your roster")
    async def rankup(self, interaction):
        await interaction.response.send_message(
            "Choose a class for rankup suggestions:",
            view=_RankupClassSelectView(self),
            ephemeral=True,
        )

    @app_commands.command(name="awaken", description="Suggest awakening candidates from your roster")
    async def awaken(self, interaction):
        await interaction.response.send_modal(_RosterAwakenModal(self))

    # -------------------------
    # /roster remove
    # -------------------------
    @app_commands.command(name="remove", description="Remove a champion from your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def remove(self, interaction, champion: str, hargs: Optional[str] = None):
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        users = ensure_user_manager(self.core)
        try:
            removed = users.remove_champion(interaction.user.id, champion, rarity)
        except Exception:
            log.exception("Failed to remove champion from roster")
            removed = 0

        if removed == 0:
            await interaction.response.send_message("No matching champion found in your roster.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Removed {removed} entries for `{champion}`.")

    # -------------------------
    # /roster update
    # -------------------------
    @app_commands.command(name="update", description="Update a champion entry in your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def update(self, interaction, champion: str, hargs: str):
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        if entry.get("rarity") is None:
            await interaction.response.send_message("Updating a champion requires rarity (e.g., `6*`).", ephemeral=True)
            return

        users = ensure_user_manager(self.core)
        try:
            updated = users.update_champion(
                interaction.user.id,
                champ_slug=champion,
                rarity=entry["rarity"],
                rank=entry.get("rank"),
                sig=entry.get("sig"),
                tags=entry.get("tags"),
            )
        except Exception:
            log.exception("Failed to update champion")
            updated = False

        if not updated:
            await interaction.response.send_message("Champion not found in your roster.", ephemeral=True)
            return

        cache = getattr(self.core, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        try:
            embed = await CDTEmbed.roster_entry_embed(interaction, champ, {
                "rarity": entry["rarity"],
                "rank": entry.get("rank") or 0,
                "sig": entry.get("sig") or 0,
                "tags": entry.get("tags") or [],
                "ascended": entry.get("ascended") or 0
            })
        except Exception:
            embed = None

        await interaction.response.send_message(f"Updated **{champ.get('name','Unknown') if champ else champion}**.", embed=embed)

    # -------------------------
    # /roster list
    # -------------------------
    @app_commands.command(name="list", description="List your roster with optional filters")
    async def list(self, interaction, hargs: Optional[str] = None):
        raw_hargs = str(hargs or "").strip()
        sender = interaction.response.send_message
        try:
            await interaction.response.defer(ephemeral=False)
            sender = interaction.followup.send if getattr(interaction.response, "is_done", lambda: False)() else interaction.response.send_message
        except Exception:
            # If defer fails, fall back to direct response attempt.
            sender = interaction.response.send_message

        try:
            target_user, cleaned_hargs = await self._resolve_target_for_list(interaction, raw_hargs)
            parsed = parse_hargs(cleaned_hargs or "")
            pager = await self._build_roster_list_pager(target_user, cleaned_hargs or "", parsed, author_for_controls=interaction.user)

            if not pager:
                await sender("No roster entries match your filters.", ephemeral=True)
                return

            try:
                await sender(embed=pager.pages[0], view=pager)
            except Exception:
                # fallback: send simple list
                names = []
                for page in pager.pages[:50]:
                    names.append(page.get("title") if isinstance(page, dict) else getattr(page, "title", None) or "Entry")
                await sender(f"Matches ({len(pager.pages)}): {', '.join(names)}", ephemeral=True)
        except Exception:
            log.exception("slash roster list failed")
            try:
                await sender("Roster list failed; please try again.", ephemeral=True)
            except Exception:
                pass

    # -------------------------
    # /roster export
    # -------------------------
    @app_commands.command(name="export", description="Export your roster as JSON")
    async def export(self, interaction):
        users = ensure_user_manager(self.core)
        data = users.export(interaction.user.id) if users else {}
        import discord
        json_text = discord.utils.escape_markdown(str(data))
        await interaction.response.send_message(f"Your roster data:\n```json\n{json_text}\n```")

    @app_commands.command(name="import", description="Import a roster from a Cocpit CSV export")
    async def import_roster(self, interaction, file: Attachment):
        try:
            payload = await file.read()
            text = payload.decode("utf-8-sig", errors="replace")
            entries = parse_roster_entries_from_input(text, getattr(self.core, "cache", None))
            result = import_roster_entries(self.core, interaction.user.id, entries)
        except Exception as exc:
            log.exception("slash roster import failed")
            await interaction.response.send_message(f"Failed to import roster CSV: {exc}", ephemeral=True)
            return

        imported = result.get("imported", 0)
        errors = result.get("errors", []) or []
        message = f"Imported {imported} roster entr{'y' if imported == 1 else 'ies'} from {getattr(file, 'filename', 'upload')}."
        if errors:
            message = f"{message}\nFirst error: {errors[0]}"
        await interaction.response.send_message(message, ephemeral=True)

    # -------------------------
    # /roster clear
    # -------------------------
    @app_commands.command(name="clear", description="Clear your entire roster")
    async def clear(self, interaction):
        users = ensure_user_manager(self.core)
        if users:
            users.delete_user(interaction.user.id)
        await interaction.response.send_message("Your roster has been cleared.")

# Cog wrapper for slash roster group
class RosterSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._group: Optional[_RosterGroup] = None

    async def cog_load(self):
        # Resolve core if present so the group can access cache/config
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _RosterGroup(core or self.bot)
            try:
                self.bot.tree.add_command(self._group)
            except Exception:
                log.exception("Failed to add Roster group to tree")
        except Exception:
            log.exception("Failed to initialize Roster group")

    async def cog_unload(self):
        try:
            if self._group:
                self.bot.tree.remove_command(self._group.name)
        except Exception:
            log.exception("Failed to remove Roster group from tree")

    @property
    def group(self) -> Optional[_RosterGroup]:
        return self._group


async def setup(bot):
    try:
        await bot.add_cog(RosterSlashCog(bot))
    except Exception:
        log.exception("Failed to add RosterSlashCog")


class _RosterRankupModal(ui.Modal):
    def __init__(self, group: _RosterGroup, class_filter: str):
        self.group = group
        self.class_filter_value = str(class_filter or "all").strip().lower() or "all"
        class_title = "All" if self.class_filter_value == "all" else self.class_filter_value.title()
        super().__init__(title=f"Rankup: {class_title}")
        self.stars = ui.TextInput(label="Star tier", placeholder="7", default="7")
        self.target_rank = ui.TextInput(label="Target rank", placeholder="3", default="3")
        self.target_per_class = ui.TextInput(
            label="Target per class (optional)",
            placeholder="2",
            default="",
            required=False,
        )
        self.add_item(self.stars)
        self.add_item(self.target_rank)
        self.add_item(self.target_per_class)

    async def on_submit(self, interaction):
        cls = self.class_filter_value
        if cls not in ROSTER_CLASSES and cls != "all":
            await interaction.response.send_message(
                "Invalid class. Use `all`, `science`, `skill`, `mutant`, `tech`, `cosmic`, or `mystic`.",
                ephemeral=True,
            )
            return
        try:
            stars = int((self.stars.value or "7").strip() or 7)
            target_rank = int((self.target_rank.value or "3").strip() or 3)
        except ValueError:
            await interaction.response.send_message("Stars and target rank must be numbers.", ephemeral=True)
            return
        if stars < 1 or stars > 7:
            await interaction.response.send_message("Star tier must be between 1 and 7.", ephemeral=True)
            return
        if target_rank < 1 or target_rank > 10:
            await interaction.response.send_message("Target rank must be between 1 and 10.", ephemeral=True)
            return

        target_per_class_text = str(self.target_per_class.value or "").strip()
        try:
            target_per_class = int(target_per_class_text) if target_per_class_text else 0
        except ValueError:
            await interaction.response.send_message("Target per class must be a number.", ephemeral=True)
            return
        if target_per_class < 0 or target_per_class > 20:
            await interaction.response.send_message("Target per class must be between 0 and 20.", ephemeral=True)
            return

        await self.group._run_rankup_suggestions(interaction, cls, stars, target_rank, target_per_class)


class _RankupClassButton(ui.Button):
    def __init__(self, group: _RosterGroup, class_filter: str):
        label = "All" if class_filter == "all" else class_filter.title()
        row_map = {
            "cosmic": 0,
            "mystic": 0,
            "mutant": 0,
            "tech": 1,
            "skill": 1,
            "science": 1,
            "all": 2,
        }
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=row_map.get(class_filter, 2))
        self.group = group
        self.class_filter = class_filter

    async def callback(self, interaction):
        await interaction.response.send_modal(_RosterRankupModal(self.group, self.class_filter))


class _RankupClassSelectView(ui.View):
    def __init__(self, group: _RosterGroup):
        super().__init__(timeout=120)
        for class_filter in ("cosmic", "mystic", "mutant", "tech", "skill", "science", "all"):
            self.add_item(_RankupClassButton(group, class_filter))


class _RosterAwakenModal(ui.Modal):
    def __init__(self, group: _RosterGroup):
        self.group = group
        super().__init__(title="Roster Awaken Suggestions")
        self.class_filter = ui.TextInput(
            label="Class (all/science/skill/etc)",
            placeholder="all",
            default="all",
            required=False,
        )
        self.stars = ui.TextInput(label="Star tier", placeholder="7", default="7")
        self.min_rank = ui.TextInput(label="Min rank", placeholder="3", default="3")
        self.target_per_class = ui.TextInput(
            label="Target per class (optional)",
            placeholder="2",
            default="",
            required=False,
        )
        self.add_item(self.class_filter)
        self.add_item(self.stars)
        self.add_item(self.min_rank)
        self.add_item(self.target_per_class)

    async def on_submit(self, interaction):
        cls = str(self.class_filter.value or "all").strip().lower() or "all"
        if cls not in ROSTER_CLASSES and cls != "all":
            await interaction.response.send_message(
                "Invalid class. Use `all`, `science`, `skill`, `mutant`, `tech`, `cosmic`, or `mystic`.",
                ephemeral=True,
            )
            return
        try:
            stars = int((self.stars.value or "7").strip() or 7)
            min_rank = int((self.min_rank.value or "3").strip() or 3)
        except ValueError:
            await interaction.response.send_message("Stars and min rank must be numbers.", ephemeral=True)
            return
        if stars < 1 or stars > 7:
            await interaction.response.send_message("Star tier must be between 1 and 7.", ephemeral=True)
            return
        if min_rank < 1 or min_rank > 10:
            await interaction.response.send_message("Min rank must be between 1 and 10.", ephemeral=True)
            return

        target_per_class_text = str(self.target_per_class.value or "").strip()
        try:
            target_per_class = int(target_per_class_text) if target_per_class_text else 0
        except ValueError:
            await interaction.response.send_message("Target per class must be a number.", ephemeral=True)
            return
        if target_per_class < 0 or target_per_class > 20:
            await interaction.response.send_message("Target per class must be between 0 and 20.", ephemeral=True)
            return

        await self.group._run_awaken_suggestions(interaction, cls, stars, min_rank, target_per_class)
