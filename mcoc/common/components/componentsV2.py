# Path: mcoc/common/components/componentsV2.py
# File-Version: 1.0
# File-Id: ee93b542-c1e2-4240-96c2-f53d5dd1b018
# Purpose: Provide helpers for building branded embeds and Discord Components V2 views.
# Public-API: CDTEmbed, _get_author_info, _brand_footer, _is_valid_http_url
# Last-Modified: 2026-09-01
"""
CDTv2 — CollectorDevTeam branded embed + components helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Keep the runtime import optional while giving Pylance valid type information.
# The runtime value is always defined before the guard below.
discord = None
discord_commands = None

if TYPE_CHECKING:
    from discord import Embed as DiscordEmbed
    from discord.ui import View as DiscordView
else:
    DiscordEmbed = Any
    DiscordView = Any

# Use aliases for annotations so static analysis does not treat runtime variables
# as invalid type expressions when discord is optionally unavailable.
Embed = DiscordEmbed
View = DiscordView
Interaction = Any
Button = Any

try:
    import discord as _discord
    from discord import Embed as DiscordEmbed
    from discord.ui import View as DiscordView
    discord = _discord
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    discord = None
    DiscordEmbed = Any
    DiscordView = Any

Embed = DiscordEmbed
View = DiscordView

try:
    from discord.ext import commands as discord_commands
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    discord_commands = None

try:
    from redbot.logging import log
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    import logging
    log = logging.getLogger("red.mcoc.components")

CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"
DOCS_URL = "https://github.com/CollectorDevTeam/CollectorBot"
IMPORT_HELP_URL = ""
CDT_FOOTER_TAG = " | CollectorBot by CollectorDevTeam"
CDT_FOOTER_TEXT = "Collector | Contest of Champions | CollectorDevTeam"

CLASS_COLOR_MAP = {
    "superior": 0x03F193,
    "all": 0x03F193,
    "tech": 0x0033FF,
    "skill": 0xDB1200,
    "mutant": 0xFFD400,
    "mystic": 0x7F0DA8,
    "cosmic": 0x2799F7,
    "science": 0x0B8C13,
    "collector_gold": 0xFFD700,
    "default": 0xFFD700,
}

NAMED_COLOR_MAP = {
    "teal": 0x03F193,
    "all": 0x03F193,
    "blue": 0x0033FF,
    "red": 0xDB1200,
    "yellow": 0xFFD400,
    "purple": 0x7F0DA8,
    "cyan": 0x2799F7,
    "green": 0x0B8C13,
    "gold": 0xFFD700,
    "default": 0xFFD700,
}


def _get_author_info(ctx_or_author: Any) -> Tuple[str, Optional[str]]:
    if ctx_or_author is None:
        return ("Collector", None)
    author = getattr(ctx_or_author, "author", ctx_or_author)
    name = getattr(author, "display_name", None) or getattr(author, "name", "Collector")
    avatar = None
    try:
        av = getattr(author, "avatar", None)
        if av is not None:
            avatar = getattr(av, "url", None) or str(av)
    except Exception:
        avatar = None
    return (name, avatar)


def _brand_footer() -> Dict[str, Any]:
    return {"text": CDT_FOOTER_TEXT, "icon_url": CDT_LOGO}


def _is_valid_http_url(url: Optional[str]) -> bool:
    try:
        if not url or not isinstance(url, str):
            return False
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


if discord is None:
    class CDTEmbed:
        @classmethod
        def embed(cls, ctx_or_author=None, **kwargs):
            return {
                "title": kwargs.get("title", ""),
                "description": kwargs.get("description", ""),
                "footer": {"text": kwargs.get("footer_text") or ""},
            }

        @classmethod
        def add_field(cls, ctx_or_author, emb, *, name, value, inline=True):
            if isinstance(emb, dict):
                emb.setdefault("fields", []).append({"name": name, "value": value, "inline": inline})
            return emb

        @classmethod
        def set_footer(cls, ctx_or_author, emb, *, text=None, icon_url=None):
            if isinstance(emb, dict):
                emb["footer"] = {"text": text or "", "icon_url": icon_url}
            return emb

        @classmethod
        def brand_view(cls):
            return None

        @classmethod
        def champion_embed(cls, ctx_or_author=None, champ=None):
            return {"title": (champ or {}).get("name", "Unknown"), "description": "Discord runtime unavailable"}

        @classmethod
        def roster_entry_embed(cls, ctx_or_author=None, champ=None, entry=None):
            return {"title": (champ or {}).get("name", "Unknown"), "description": "Discord runtime unavailable"}

        @classmethod
        def tag_list_embed(cls, ctx_or_author=None, tag="", champions=None):
            return {"title": f"#{tag}", "description": "Discord runtime unavailable"}

    class CDTConfirm:
        def __init__(self, *, timeout: float = 30.0, ephemeral: bool = True, confirm_label: str = "Yes", cancel_label: str = "No"):
            self.value = None
            self.timeout = timeout
            self.ephemeral = ephemeral
            self.confirm_label = confirm_label
            self.cancel_label = cancel_label

        async def wait_result(self) -> Optional[bool]:
            return self.value

    class CDTPagesMenu:
        def __init__(self, pages: list, *, author: Optional[Any] = None, timeout: float = 120.0, show_brand: bool = True):
            self.pages = pages
            self.author = author
            self.timeout = timeout
            self.show_brand = show_brand

        async def start(self, ctx):
            return None

    cdt_embed = CDTEmbed.embed
    champion_embed = CDTEmbed.champion_embed
    roster_entry_embed = CDTEmbed.roster_entry_embed
    tag_list_embed = CDTEmbed.tag_list_embed
    brand_view = CDTEmbed.brand_view

else:
    class CDTEmbed:
        """Static helpers to build branded embeds and optional component Views."""

        @classmethod
        def _get_color_value(cls, ctx_or_author: Any = None, color_param: Any = None, class_name: Optional[str] = None) -> int:
            if isinstance(color_param, int):
                return color_param
            if isinstance(color_param, str):
                try:
                    s = color_param.strip().lstrip("#")
                    return int(s, 16)
                except Exception:
                    pass
            if isinstance(class_name, str):
                key = class_name.lower()
                if key in CLASS_COLOR_MAP:
                    return CLASS_COLOR_MAP[key]
            try:
                author = getattr(ctx_or_author, "author", ctx_or_author)
                if author is not None:
                    col = getattr(author, "color", None)
                    if isinstance(col, int):
                        return col
                    if hasattr(col, "value"):
                        try:
                            return int(getattr(col, "value"))
                        except Exception:
                            pass
                    try:
                        return int(col)
                    except Exception:
                        pass
            except Exception:
                pass
            return CLASS_COLOR_MAP.get("default", 0xD4AF37)

        @classmethod
        def embed(cls, ctx_or_author=None, *, title="", description="", color=None,
                  image=None, thumbnail=None, url=None, footer=None,
                  footer_text=None, footer_icon=CDT_ICON):
            if color is None:
                author = getattr(ctx_or_author, "author", ctx_or_author)
                color = getattr(author, "color", None) or discord.Color.gold()
            else:
                try:
                    color = cls._get_color_value(ctx_or_author, color)
                except Exception:
                    pass
            emb = Embed(title=title, description=description, color=color, url=url)
            name, avatar = _get_author_info(ctx_or_author)
            if avatar:
                try:
                    emb.set_author(name=name, icon_url=avatar)
                except Exception:
                    emb.set_author(name=name)
            else:
                emb.set_author(name=name)
            if image and _is_valid_http_url(image):
                try:
                    emb.set_image(url=image)
                except Exception:
                    pass
            if thumbnail and _is_valid_http_url(thumbnail):
                try:
                    emb.set_thumbnail(url=thumbnail)
                except Exception:
                    pass
            try:
                if footer and isinstance(footer, dict):
                    emb.set_footer(text=footer.get("text"), icon_url=footer.get("icon_url"))
                else:
                    emb.set_footer(text=footer_text or CDT_FOOTER_TEXT, icon_url=footer_icon)
            except Exception:
                try:
                    emb.set_footer(text=footer_text or CDT_FOOTER_TEXT)
                except Exception:
                    pass
            return emb

        @classmethod
        def add_field(cls, ctx_or_author, emb, *, name, value, inline=True):
            try:
                emb.add_field(name=name, value=value, inline=inline)
            except Exception:
                try:
                    desc = getattr(emb, "description", "") or ""
                    if desc:
                        emb.description = f"{desc}\n\n**{name}**\n{value}"
                    else:
                        emb.description = f"**{name}**\n{value}"
                except Exception:
                    pass
            return emb

        @classmethod
        def set_footer(cls, ctx_or_author, emb, *, text=None, icon_url=None):
            try:
                emb.set_footer(text=text or CDT_FOOTER_TEXT, icon_url=icon_url or CDT_ICON)
            except Exception:
                try:
                    emb.set_footer(text=text or CDT_FOOTER_TEXT)
                except Exception:
                    pass
            return emb

        @classmethod
        def set_author(cls, ctx_or_author: Any, emb: Any, *, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> Any:
            try:
                if icon_url and not _is_valid_http_url(icon_url):
                    icon_url = None
                emb.set_author(name=name, url=url, icon_url=icon_url)
            except Exception:
                try:
                    emb.set_author(name=name)
                except Exception:
                    pass
            return emb

        @classmethod
        def insert_field_at(cls, ctx_or_author: Any, emb: Any, index: int, *, name: str, value: str, inline: bool = True) -> Any:
            try:
                emb.insert_field_at(index=index, name=name, value=value, inline=inline)
            except Exception:
                pass
            return emb

        @classmethod
        def set_field_at(cls, ctx_or_author: Any, emb: Any, index: int, *, name: str, value: str, inline: bool = True) -> Any:
            try:
                emb.set_field_at(index=index, name=name, value=value, inline=inline)
            except Exception:
                pass
            return emb

        @classmethod
        def champion_embed(cls, ctx_or_author: Any, champ: Dict[str, Any]) -> Any:
            name = champ.get("name", "Unknown")
            cls_name = (champ.get("class") or "?").title()
            tags = ", ".join(champ.get("tags", []) or []) or "None"
            desc = f"Class: {cls_name}\nTags: {tags}"
            emb = CDTEmbed.embed(ctx_or_author, title=name, description=desc, thumbnail=(champ.get("images") or {}).get("portrait"))
            abilities = champ.get("abilities", []) or []
            if abilities:
                lines = []
                for a in abilities:
                    lines.append(f"• {a.get('name', '?')} ({a.get('type', 'full')})")
                CDTEmbed.add_field(ctx_or_author, emb, name="Abilities", value="\n".join(lines), inline=False)
            immunities = champ.get("immunities", []) or []
            if immunities:
                lines = []
                for i in immunities:
                    note = i.get("note")
                    if note:
                        lines.append(f"• {i.get('name', '?')} ({i.get('type', 'full')}) — {note}")
                    else:
                        lines.append(f"• {i.get('name', '?')} ({i.get('type', 'full')})")
                CDTEmbed.add_field(ctx_or_author, emb, name="Immunities", value="\n".join(lines), inline=False)
            return emb

        @classmethod
        def roster_entry_embed(cls, ctx_or_author: Any, champ: Dict[str, Any], entry: Dict[str, Any]) -> Any:
            rarity = entry.get("rarity", "?")
            rank = entry.get("rank", "?")
            sig = entry.get("sig", "?")
            tags = entry.get("tags", []) or []
            desc = (
                f"Rarity: {rarity}★\n"
                f"Rank: {rank}\n"
                f"Signature: {sig}\n"
                f"Tags: {', '.join(tags) if tags else 'None'}"
            )
            return CDTEmbed.embed(ctx_or_author, title=champ.get("name", "Unknown"), description=desc, thumbnail=(champ.get("images") or {}).get("portrait"))

        @classmethod
        def tag_list_embed(cls, ctx_or_author: Any, tag: str, champions: List[Dict[str, Any]]) -> Any:
            emb = CDTEmbed.embed(ctx_or_author, title=f"Champions with #{tag}", description=f"{len(champions)} champions match this tag.")
            lines = [c.get("name", "Unknown") for c in champions or []]
            try:
                CDTEmbed.add_field(ctx_or_author, emb, name="Matches", value="\n".join(lines) or "None", inline=False)
            except Exception:
                pass
            return emb

        @classmethod
        def brand_view(cls, *, include_patreon: bool = True, include_docs: bool = True, include_import_help: bool = True, patreon_label: str = "Support on Patreon", docs_label: str = "Docs", import_label: str = "Import Help") -> Any:
            view = discord.ui.View()
            if include_patreon and _is_valid_http_url(PATREON):
                view.add_item(discord.ui.Button(label=patreon_label, url=PATREON, style=discord.ButtonStyle.link))
            if include_docs and _is_valid_http_url(DOCS_URL):
                view.add_item(discord.ui.Button(label=docs_label, url=DOCS_URL, style=discord.ButtonStyle.link))
            if include_import_help and _is_valid_http_url(IMPORT_HELP_URL):
                view.add_item(discord.ui.Button(label=import_label, url=IMPORT_HELP_URL, style=discord.ButtonStyle.link))
            return view

        @classmethod
        def set_image(cls, embed: Any, image_url: str) -> None:
            try:
                embed.set_image(url=image_url)
            except Exception:
                pass

        @classmethod
        def set_url(cls, embed: Any, url: str) -> None:
            try:
                embed.url = url
            except Exception:
                pass

    class CDTConfirm(discord.ui.View):
        def __init__(self, *, timeout: float = 30.0, ephemeral: bool = True, confirm_label: str = "Yes", cancel_label: str = "No"):
            super().__init__(timeout=timeout)
            self.value: Optional[bool] = None
            self.ephemeral = ephemeral
            self.confirm_label = confirm_label
            self.cancel_label = cancel_label

            yes_button = discord.ui.Button(label=confirm_label, style=discord.ButtonStyle.success)
            yes_button.callback = self._confirm_callback
            self.add_item(yes_button)

            no_button = discord.ui.Button(label=cancel_label, style=discord.ButtonStyle.secondary)
            no_button.callback = self._cancel_callback
            self.add_item(no_button)

        async def _confirm_callback(self, interaction: Any):
            self.value = True
            for item in self.children:
                item.disabled = True
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass
            self.stop()

        async def _cancel_callback(self, interaction: Any):
            self.value = False
            for item in self.children:
                item.disabled = True
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass
            self.stop()

        async def wait_result(self) -> Optional[bool]:
            await self.wait()
            return self.value

    class CDTPagesMenu(View):
        def __init__(self, pages: list, *, author: Optional[Any] = None, timeout: float = 120.0, show_brand: bool = True, show_filter: bool = True, filter_hint: Optional[str] = None):
            super().__init__(timeout=timeout)
            self.pages = pages
            self.index = 0
            self.author = author
            self.message: Optional[Any] = None
            self.show_brand = show_brand
            self.show_filter = show_filter
            self.filter_hint = filter_hint or (
                "Use filter tokens like #bleed, mystic, cosmic, 6*, 7-star, or a champion name. "
                "Class + tier + tag filters combine as AND across buckets."
            )

            first_button = discord.ui.Button(emoji="⏮️", style=discord.ButtonStyle.secondary)
            first_button.callback = self._first_callback
            self.add_item(first_button)

            prev_button = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.secondary)
            prev_button.callback = self._prev_callback
            self.add_item(prev_button)

            next_button = discord.ui.Button(emoji="▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self._next_callback
            self.add_item(next_button)

            last_button = discord.ui.Button(emoji="⏭️", style=discord.ButtonStyle.secondary)
            last_button.callback = self._last_callback
            self.add_item(last_button)

            close_button = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger)
            close_button.callback = self._close_callback
            self.add_item(close_button)

            if self.show_filter:
                filter_button = discord.ui.Button(label="Filter", style=discord.ButtonStyle.primary)
                filter_button.callback = self._filter_callback
                self.add_item(filter_button)

        async def _render_page(self):
            page = self.pages[self.index]
            if isinstance(page, Embed):
                emb = page
            elif isinstance(page, dict):
                emb = Embed(title=page.get("title", "Page"), description=page.get("description", ""))
            else:
                emb = Embed(title="Page", description=str(page))
            try:
                base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
                footer_text = f"{base} • Page {self.index + 1} of {len(self.pages)}{CDT_FOOTER_TAG}" if base else f"Page {self.index + 1} of {len(self.pages)}{CDT_FOOTER_TAG}"
                emb.set_footer(text=footer_text, icon_url=CDT_ICON)
            except Exception:
                try:
                    emb.set_footer(text=f"Page {self.index + 1} of {len(self.pages)}", icon_url=CDT_ICON)
                except Exception:
                    pass
            return emb

        def _embed_size_bytes(self, emb: Any) -> int:
            try:
                payload = emb.to_dict()
                import json
                return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
            except Exception:
                return 0

        def _sanitize_embed_for_discord(self, emb: Any) -> Any:
            try:
                if self._embed_size_bytes(emb) <= 5500:
                    pass
                else:
                    try:
                        emb.clear_fields()
                        emb.description = "This page is too large for one Discord embed. Please narrow the filters or use a smaller range."
                        emb.set_image(url=None)
                        emb.set_thumbnail(url=None)
                        return emb
                    except Exception:
                        return emb
            except Exception:
                return emb

            try:
                for field in list(getattr(emb, "fields", []) or []):
                    try:
                        if len(str(field.value)) > 1024:
                            field.value = str(field.value)[:1021] + "..."
                    except Exception:
                        pass
                if len(str(emb.description or "")) > 4096:
                    emb.description = str(emb.description)[:4093] + "..."
            except Exception:
                pass
            return emb

        async def start(self, ctx):
            emb = await self._render_page()
            emb = self._sanitize_embed_for_discord(emb)
            if self.show_brand:
                try:
                    brand = CDTEmbed.brand_view()
                    for item in getattr(brand, "children", []):
                        try:
                            self.add_item(item)
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                if hasattr(ctx, "send"):
                    self.message = await ctx.send(embed=emb, view=self)
                else:
                    await ctx.response.send_message(embed=emb, view=self)
                    self.message = await ctx.original_response()
            except Exception:
                try:
                    log.exception("CDTPagesMenu.start failed; retrying with sanitized embed")
                    emb.set_image(url=None)
                    emb.set_thumbnail(url=None)
                    emb.description = "This page is too large for one Discord embed. Please narrow the filters or use a smaller range."
                    emb.clear_fields()
                    if hasattr(ctx, "send"):
                        self.message = await ctx.send(embed=emb, view=self)
                    else:
                        await ctx.response.send_message(embed=emb, view=self)
                        self.message = await ctx.original_response()
                except Exception:
                    log.exception("CDTPagesMenu.start retry failed; aborting")
                    raise

        async def _first_callback(self, interaction: Any):
            self.index = 0
            await interaction.response.edit_message(embed=await self._render_page(), view=self)

        async def _prev_callback(self, interaction: Any):
            self.index = max(0, self.index - 1)
            await interaction.response.edit_message(embed=await self._render_page(), view=self)

        async def _next_callback(self, interaction: Any):
            self.index = min(len(self.pages) - 1, self.index + 1)
            await interaction.response.edit_message(embed=await self._render_page(), view=self)

        async def _last_callback(self, interaction: Any):
            self.index = len(self.pages) - 1
            await interaction.response.edit_message(embed=await self._render_page(), view=self)

        async def _close_callback(self, interaction: Any):
            for item in self.children:
                item.disabled = True
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass
            self.stop()

        async def _filter_callback(self, interaction: Any):
            handler = getattr(self, "filter_handler", None)
            if callable(handler):
                try:
                    await handler(self, interaction)
                    return
                except Exception:
                    pass
            try:
                await interaction.response.send_message(
                    self.filter_hint,
                    ephemeral=True,
                )
            except Exception:
                try:
                    await interaction.followup.send(self.filter_hint, ephemeral=True)
                except Exception:
                    pass

        async def on_timeout(self):
            try:
                if self.message:
                    for item in self.children:
                        item.disabled = True
                    await self.message.edit(view=self)
            except Exception:
                pass

ctd_embed = CDTEmbed.embed
champion_embed = CDTEmbed.champion_embed
roster_entry_embed = CDTEmbed.roster_entry_embed
tag_list_embed = CDTEmbed.tag_list_embed
brand_view = CDTEmbed.brand_view
