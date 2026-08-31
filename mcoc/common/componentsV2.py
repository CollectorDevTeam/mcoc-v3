# mcoc/common/componentsV2.py
"""
CDTv2 — CollectorDevTeam branded embed + components helpers (Discord Components V2 friendly)
"""

from typing import Any, Dict, List, Optional, Tuple, Sequence
from urllib.parse import urlparse
import discord
from typing import Optional
from redbot.logging import log

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

log.debug("ComponentsV2 module loaded.")

# -------------------------------------
# HELPERS
# -------------------------------------
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
    return {
        "text": CDT_FOOTER_TEXT,
        "icon_url": CDT_LOGO,
    }


def _is_valid_http_url(url: Optional[str]) -> bool:
    try:
        if not url or not isinstance(url, str):
            return False
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


class CDTEmbed:
    """
    Static helpers to build branded embeds and optional component Views.
    """

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

        # Resolve color
        if color is None:
            author = getattr(ctx_or_author, "author", ctx_or_author)
            color = getattr(author, "color", None) or discord.Color.gold()

        emb = discord.Embed(title=title, description=description, color=color, url=url)

        # Author
        name, avatar = _get_author_info(ctx_or_author)
        if avatar:
            try:
                emb.set_author(name=name, icon_url=avatar)
            except Exception:
                emb.set_author(name=name)
        else:
            emb.set_author(name=name)

        # Images
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

        # Footer
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
        # Fixed: call the embed API instead of recursing
        try:
            emb.add_field(name=name, value=value, inline=inline)
        except Exception:
            try:
                # fallback: insert as description append if add_field fails
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
        # Fixed: use discord.Embed.set_footer signature
        try:
            emb.set_footer(text=text or CDT_FOOTER_TEXT, icon_url=icon_url or CDT_ICON)
        except Exception:
            try:
                emb.set_footer(text=text or CDT_FOOTER_TEXT)
            except Exception:
                pass
        return emb

    @classmethod
    def set_author(cls, ctx_or_author: Any, emb: "discord.Embed", *, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> "discord.Embed":
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
    def insert_field_at(cls, ctx_or_author: Any, emb: "discord.Embed", index: int, *, name: str, value: str, inline: bool = True) -> "discord.Embed":
        try:
            emb.insert_field_at(index=index, name=name, value=value, inline=inline)
        except Exception:
            pass
        return emb

    @classmethod
    def set_field_at(cls, ctx_or_author: Any, emb: "discord.Embed", index: int, *, name: str, value: str, inline: bool = True) -> "discord.Embed":
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

        emb = CDTEmbed.embed(
            ctx_or_author,
            title=name,
            description=desc,
            thumbnail=(champ.get("images") or {}).get("portrait"),
        )

        abilities = champ.get("abilities", []) or []
        if abilities:
            lines = []
            for a in abilities:
                t = a.get("type", "full")
                aname = a.get("name", "?")
                lines.append(f"• {aname} ({t})")
            try:
                CDTEmbed.add_field(ctx_or_author, emb, name="Abilities", value="\n".join(lines), inline=False)
            except Exception:
                pass

        immunities = champ.get("immunities", []) or []
        if immunities:
            lines = []
            for i in immunities:
                t = i.get("type", "full")
                iname = i.get("name", "?")
                note = i.get("note")
                if note:
                    lines.append(f"• {iname} ({t}) — {note}")
                else:
                    lines.append(f"• {iname} ({t})")
            try:
                CDTEmbed.add_field(ctx_or_author, emb, name="Immunities", value="\n".join(lines), inline=False)
            except Exception:
                pass

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

        emb = CDTEmbed.embed(
            ctx_or_author,
            title=champ.get("name", "Unknown"),
            description=desc,
            thumbnail=(champ.get("images") or {}).get("portrait"),
        )
        return emb

    @classmethod
    def tag_list_embed(cls, ctx_or_author: Any, tag: str, champions: List[Dict[str, Any]]) -> Any:
        emb = CDTEmbed.embed(
            ctx_or_author,
            title=f"Champions with #{tag}",
            description=f"{len(champions)} champions match this tag.",
        )
        lines = [c.get("name", "Unknown") for c in champions or []]
        try:
            CDTEmbed.add_field(ctx_or_author, emb, name="Matches", value="\n".join(lines) or "None", inline=False)
        except Exception:
            pass
        return emb

    @classmethod
    def brand_view(cls,
                   *,
                   include_patreon: bool = True,
                   include_docs: bool = True,
                   include_import_help: bool = True,
                   patreon_label: str = "Support on Patreon",
                   docs_label: str = "Docs",
                   import_label: str = "Import Help",
                   ) -> Any:
        try:
            import discord as _discord
        except Exception:
            buttons = []
            if include_patreon:
                buttons.append({"label": patreon_label, "url": PATREON})
            if include_docs:
                buttons.append({"label": docs_label, "url": DOCS_URL})
            if include_import_help:
                buttons.append({"label": import_label, "url": IMPORT_HELP_URL})
            return buttons

        view = _discord.ui.View()
        if include_patreon:
            try:
                if _is_valid_http_url(PATREON):
                    view.add_item(_discord.ui.Button(label=patreon_label, url=PATREON, style=_discord.ButtonStyle.link))
            except Exception:
                pass
        if include_docs:
            try:
                if _is_valid_http_url(DOCS_URL):
                    view.add_item(_discord.ui.Button(label=docs_label, url=DOCS_URL, style=_discord.ButtonStyle.link))
            except Exception:
                pass
        if include_import_help:
            try:
                if _is_valid_http_url(IMPORT_HELP_URL):
                    view.add_item(_discord.ui.Button(label=import_label, url=IMPORT_HELP_URL, style=_discord.ButtonStyle.link))
            except Exception:
                pass

        return view

    @classmethod
    def set_image(cls, embed: "discord.Embed", image_url: str) -> None:
        try:
            embed.set_image(url=image_url)
        except Exception:
            pass

    @classmethod
    def set_url(cls, embed: "discord.Embed", url: str) -> None:
        try:
            embed.url = url
        except Exception:
            pass


cdt_embed = CDTEmbed.embed
champion_embed = CDTEmbed.champion_embed
roster_entry_embed = CDTEmbed.roster_entry_embed
tag_list_embed = CDTEmbed.tag_list_embed
brand_view = CDTEmbed.brand_view


class CDTConfirm(discord.ui.View):
    def __init__(self, *, timeout: float = 30.0, ephemeral: bool = True, confirm_label: str = "Yes", cancel_label: str = "No"):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.ephemeral = ephemeral
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
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


class CDTPagesMenu(discord.ui.View):
    def __init__(self, pages: list, *, author: Optional[discord.abc.User] = None, timeout: float = 120.0, show_brand: bool = True):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.index = 0
        self.author = author
        self.message: Optional[discord.Message] = None
        self.show_brand = show_brand

    async def _render_page(self):
        page = self.pages[self.index]
        if isinstance(page, discord.Embed):
            emb = page
        elif isinstance(page, dict):
            emb = discord.Embed(title=page.get("title", "Page"), description=page.get("description", ""))
        else:
            emb = discord.Embed(title="Page", description=str(page))

        try:
            base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
            if base:
                footer_text = f"{base} • Page {self.index+1} of {len(self.pages)}{CDT_FOOTER_TAG}"
            else:
                footer_text = f"Page {self.index+1} of {len(self.pages)}{CDT_FOOTER_TAG}"
            emb.set_footer(text=footer_text, icon_url=CDT_ICON)
        except Exception:
            try:
                emb.set_footer(text=f"Page {self.index+1} of {len(self.pages)}", icon_url=CDT_ICON)
            except Exception:
                pass
        return emb

    async def start(self, ctx: discord.Interaction | discord.ext.commands.Context):
        emb = await self._render_page()
        view = self
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
                self.message = await ctx.send(embed=emb, view=view)
            else:
                await ctx.response.send_message(embed=emb, view=view)
                self.message = await ctx.original_response()
        except Exception:
            try:
                log.exception("CDTPagesMenu.start failed; retrying with sanitized embed")
                try:
                    emb.set_image(url=None)
                except Exception:
                    pass
                try:
                    emb.set_thumbnail(url=None)
                except Exception:
                    pass
                if hasattr(ctx, "send"):
                    self.message = await ctx.send(embed=emb, view=view)
                else:
                    await ctx.response.send_message(embed=emb, view=view)
                    self.message = await ctx.original_response()
            except Exception:
                log.exception("CDTPagesMenu.start retry failed; aborting")
                raise

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = 0
        await interaction.response.edit_message(embed=await self._render_page(), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        await interaction.response.edit_message(embed=await self._render_page(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.pages) - 1, self.index + 1)
        await interaction.response.edit_message(embed=await self._render_page(), view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = len(self.pages) - 1
        await interaction.response.edit_message(embed=await self._render_page(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass
        self.stop()

    async def on_timeout(self):
        try:
            if self.message:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except Exception:
            pass
