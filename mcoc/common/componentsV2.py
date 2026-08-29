# mcoc/common/componentsV2.py
"""
CDTv2 — CollectorDevTeam branded embed + components helpers (Discord Components V2 friendly)

Provides:
  - CDTv2.embed(...)            -> discord.Embed (or dict fallback)
  - CDTv2.champion_embed(...)   -> embed for champion details
  - CDTv2.roster_entry_embed(...) -> embed for a roster entry
  - CDTv2.brand_view(...)       -> discord.ui.View with branded buttons (patreon, docs, import help)
  - helper functions to extract author info and to build consistent footers/headers

Designed to be a drop-in, modern replacement for mcoc/common/embeds.py with
preset styling, footer, and optional component (View) generation for V2 components.
"""

from asyncio import log
from typing import Any, Dict, List, Optional, Tuple, Sequence
from urllib.parse import urlparse
import discord
from typing import Optional
from redbot.logging import log

CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"
DOCS_URL = "https://github.com/CollectorDevTeam/CollectorBot"  # example docs link
# IMPORT_HELP_URL = "https://hook.github.io/champions/#/roster"
IMPORT_HELP_URL = ""
CDT_FOOTER_TAG = " | CollectorBot by CollectorDevTeam"
CDT_FOOTER_TEXT = "Collector | Contest of Champions | CollectorDevTeam"

# Static color palette (hex integers)
# Picked to be visually distinct and readable on Discord embeds
CLASS_COLOR_MAP = {
    "superior": 0x03F193,       # neutral teal
    "all": 0x03F193,
    "tech": 0x0033FF,      # blue
    "skill": 0xDB1200,     # red
    "mutant": 0xFFD400,    # yellow
    "mystic": 0x7F0DA8,    # purple
    "cosmic": 0x2799F7,    # blue
    "science": 0x0B8C13,   # green
    # fallback / special
    "collector_gold": 0xFFD700,  # Collector gold
    "default": 0xFFD700,   # use collector gold as default
}

NAMED_COLOR_MAP = {
    "teal": 0x03F193,       # neutral teal
    "all": 0x03F193,
    "blue": 0x0033FF,      # blue
    "red": 0xDB1200,     # red
    "yellow": 0xFFD400,    # yellow
    "purple": 0x7F0DA8,    # purple
    "cyan": 0x2799F7,    # blue
    "green": 0x0B8C13,   # green
    # fallback / special
    "gold": 0xFFD700,  # Collector gold
    "default": 0xFFD700,   # use collector gold as default
}

log.debug("ComponentsV2 module loaded.")

# -------------------------------------
# HELPERS
# -------------------------------------
# Minimal author extraction (works with Context or Member/User)
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
    """
    Return True if url is a well-formed absolute HTTP/HTTPS URL.
    """
    try:
        if not url or not isinstance(url, str):
            return False
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


# The CDTv2 helper class
class CDTEmbed:
    """
    Static helpers to build branded embeds and optional component Views.
    Use the synchronous API (no awaits required).
    """
    def _get_color_value(ctx_or_author: Any = None, color_param: Any = None, class_name: Optional[str] = None) -> int:
        """
        Resolve an integer color value for embeds without importing discord.
        Priority:
        1. explicit color_param if it's an int or hex string
        2. class_name mapping from CLASS_COLOR_MAP
        3. author's color attribute if present and convertible
        4. default collector gold
        """
        # 1) explicit color param
        if isinstance(color_param, int):
            return color_param
        if isinstance(color_param, str):
            try:
                # accept "#RRGGBB" or "RRGGBB"
                s = color_param.strip().lstrip("#")
                return int(s, 16)
            except Exception:
                pass

        # 2) class name mapping
        if isinstance(class_name, str):
            key = class_name.lower()
            if key in CLASS_COLOR_MAP:
                return CLASS_COLOR_MAP[key]

        # 3) try to extract author color if available
        try:
            author = getattr(ctx_or_author, "author", ctx_or_author)
            if author is not None:
                # some objects expose .color as an int or as an object with .value
                col = getattr(author, "color", None)
                if isinstance(col, int):
                    return col
                # discord.py Color objects often have .value or __int__
                if hasattr(col, "value"):
                    try:
                        return int(getattr(col, "value"))
                    except Exception:
                        pass
                try:
                    # fallback: try int(col) if supported
                    return int(col)
                except Exception:
                    pass
        except Exception:
            pass

        # 4) fallback
        return CLASS_COLOR_MAP.get("default", 0xD4AF37)

    @staticmethod
    def embed(
        ctx_or_author: Any = None,
        *,
        color: Any = CLASS_COLOR_MAP.get("default"),
        description: str = "",
        footer: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        thumbnail: Optional[str] = None,
        title: str = "",
        url: str = None,
        footer_text: Optional[str] = None,
        footer_icon: Optional[str] = CDT_ICON,
        # include_brand_button_row: bool = True,
    ) -> Any:
        """
        Build a branded embed. Returns a discord.Embed when discord is available,
        otherwise returns a dict fallback.

        If include_brand_button_row is True and discord is available, callers can
        also call CDTv2.brand_view() to get a View with branded buttons.
        """
        try:
            import discord
        except Exception:
            return {
                "title": title,
                "description": description,
                "color": color,
                "image": image,
                "thumbnail": thumbnail or CDT_LOGO,
                "url": url,
                "author": _get_author_info(ctx_or_author),
                "footer": footer or {
                    "text": footer_text or (CDT_FOOTER_TEXT),
                    "icon_url": footer_icon or (CDT_LOGO),
                },
            }

        # Determine color: prefer author's color if available
        if color is None:
            author = getattr(ctx_or_author, "author", ctx_or_author)
            color = getattr(author, "color", None) or discord.Color.gold()

        emb = discord.Embed(title=title, description=description, color=color, url=url)

        # Author
        display_name, avatar_url = _get_author_info(ctx_or_author)
        try:
            if avatar_url:
                emb.set_author(name=display_name, icon_url=avatar_url)
            else:
                emb.set_author(name=display_name)
        except Exception:
            try:
                emb.set_author(name=display_name)
            except Exception:
                pass

        # Images (validate)
        if image and _is_valid_http_url(image):
            try:
                emb.set_image(url=image)
            except Exception:
                pass
        try:
            if _is_valid_http_url(thumbnail or CDT_LOGO):
                emb.set_thumbnail(url=thumbnail or CDT_LOGO)
        except Exception:
            pass

        # Footer
        try:
            footer_final = footer or _brand_footer()
            emb.set_footer(text=footer_final.get("text"), icon_url=footer_final.get("icon_url", CDT_LOGO))
        except Exception:
            pass

        return emb

    # Author setter wrapper matching discord.Embed.set_author signature
    def set_author(ctx_or_author: Any, emb: "discord.Embed", *, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> "discord.Embed":
        try:
            # validate icon_url if provided
            if icon_url and not _is_valid_http_url(icon_url):
                icon_url = None
            emb.set_author(name=name, url=url, icon_url=icon_url)
        except Exception:
            try:
                emb.set_author(name=name)
            except Exception:
                pass
        return emb

    # Field helpers (add_field already existed; ensure signature parity)
    def add_field(ctx_or_author: Any, emb: "discord.Embed", *, name: str, value: str, inline: bool = True) -> "discord.Embed":
        try:
            emb.add_field(name=name, value=value, inline=inline)
        except Exception:
            pass
        return emb

    def insert_field_at(ctx_or_author: Any, emb: "discord.Embed", index: int, *, name: str, value: str, inline: bool = True) -> "discord.Embed":
        try:
            emb.insert_field_at(index=index, name=name, value=value, inline=inline)
        except Exception:
            pass
        return emb

    def set_field_at(ctx_or_author: Any, emb: "discord.Embed", index: int, *, name: str, value: str, inline: bool = True) -> "discord.Embed":
        try:
            emb.set_field_at(index=index, name=name, value=value, inline=inline)
        except Exception:
            pass
        return emb

    def set_footer(ctx_or_author: Any, emb: "discord.Embed", *, text: Optional[str] = None, icon_url: Optional[str] = None) -> "discord.Embed":
        try:
            if icon_url and not _is_valid_http_url(icon_url):
                icon_url = None
            if text is None:
                footer_final = CDT_FOOTER_TEXT
            else:
                footer_final = (text or "")
            emb.set_footer(text=footer_final, icon_url=icon_url or CDT_LOGO)
        except Exception:
            pass
        return emb


    @staticmethod
    def champion_embed(ctx_or_author: Any, champ: Dict[str, Any]) -> Any:
        """
        Champion detail embed (name, class, tags, abilities, immunities).
        """
        name = champ.get("name", "Unknown")
        cls = (champ.get("class") or "?").title()
        tags = ", ".join(champ.get("tags", []) or []) or "None"
        desc = f"Class: {cls}\nTags: {tags}"

        emb = CDTEmbed.embed(
            ctx_or_author,
            title=name,
            description=desc,
            thumbnail=(champ.get("images") or {}).get("portrait"),
        )

        # Add abilities and immunities if present (safely)
        abilities = champ.get("abilities", []) or []
        if abilities:
            lines = []
            for a in abilities:
                t = a.get("type", "full")
                aname = a.get("name", "?")
                lines.append(f"• {aname} ({t})")
            try:
                emb.add_field(name="Abilities", value="\n".join(lines), inline=False)
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
                emb.add_field(name="Immunities", value="\n".join(lines), inline=False)
            except Exception:
                pass

        return emb

    @staticmethod
    def roster_entry_embed(ctx_or_author: Any, champ: Dict[str, Any], entry: Dict[str, Any]) -> Any:
        """
        Embed for a single roster entry (champion object + user entry metadata).
        """
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

    @staticmethod
    def tag_list_embed(ctx_or_author: Any, tag: str, champions: List[Dict[str, Any]]) -> Any:
        """
        Embed listing champions for a tag.
        """
        emb = CDTEmbed.embed(
            ctx_or_author,
            title=f"Champions with #{tag}",
            description=f"{len(champions)} champions match this tag.",
        )
        lines = [c.get("name", "Unknown") for c in champions or []]
        try:
            emb.add_field(name="Matches", value="\n".join(lines) or "None", inline=False)
        except Exception:
            pass
        return emb

    @staticmethod
    def brand_view(
        *,
        include_patreon: bool = True,
        include_docs: bool = True,
        include_import_help: bool = True,
        patreon_label: str = "Support on Patreon",
        docs_label: str = "Docs",
        import_label: str = "Import Help",
    ) -> Any:
        """
        Return a discord.ui.View with branded buttons suitable for Components V2.
        If discord is not available, returns a simple list of button descriptors.
        """
        try:
            import discord
        except Exception:
            # Fallback: return a list of button dicts
            buttons = []
            if include_patreon:
                buttons.append({"label": patreon_label, "url": PATREON})
            if include_docs:
                buttons.append({"label": docs_label, "url": DOCS_URL})
            if include_import_help:
                buttons.append({"label": import_label, "url": IMPORT_HELP_URL})
            return buttons

        view = discord.ui.View()
        if include_patreon:
            try:
                if _is_valid_http_url(PATREON):
                    view.add_item(discord.ui.Button(label=patreon_label, url=PATREON, style=discord.ButtonStyle.link))
            except Exception:
                pass
        if include_docs:
            try:
                if _is_valid_http_url(DOCS_URL):
                    view.add_item(discord.ui.Button(label=docs_label, url=DOCS_URL, style=discord.ButtonStyle.link))
            except Exception:
                pass
        if include_import_help:
            try:
                if _is_valid_http_url(IMPORT_HELP_URL):
                    view.add_item(discord.ui.Button(label=import_label, url=IMPORT_HELP_URL, style=discord.ButtonStyle.link))
            except Exception:
                pass


        return view


# Backwards-compatible aliases (if other modules import these names)
cdt_embed = CDTEmbed.embed
champion_embed = CDTEmbed.champion_embed
roster_entry_embed = CDTEmbed.roster_entry_embed
tag_list_embed = CDTEmbed.tag_list_embed
brand_view = CDTEmbed.brand_view

class CDTConfirm(discord.ui.View):
    """
    Simple confirm/cancel view. Use `await ctx.send(embed=..., view=CDTConfirm())`
    and then `result = await view.wait_result()` to get True/False/None.
    """

    def __init__(self, *, timeout: float = 30.0, ephemeral: bool = True, confirm_label: str = "Yes", cancel_label: str = "No"):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.ephemeral = ephemeral
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        # disable buttons to prevent double clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        # disable buttons to prevent double clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
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

        # Build footer: preserve existing footer text if present, append page numbering and brand tag
        try:
            base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
            # prefer explicit base if present, otherwise brand text
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

    # In CDTPagesMenu._render_page: preserve existing behavior but ensure embed is a discord.Embed
    # (no change needed beyond image/thumbnail validation already applied in CDTEmbed.embed)

    # In CDTPagesMenu.start: wrap ctx.send in a try/except and retry sanitized embed
    async def start(self, ctx: discord.Interaction | discord.ext.commands.Context):
        emb = await self._render_page()
        view = self
        if self.show_brand:
            try:
                brand = CDTEmbed.brand_view()
                for item in getattr(brand, "children", []):
                    try:
                        # only add items with valid link URLs (brand_view already validated)
                        self.add_item(item)
                    except Exception:
                        pass
            except Exception:
                pass

        # Try sending; if it fails due to invalid embed content, retry with sanitized embed
        try:
            if hasattr(ctx, "send"):
                self.message = await ctx.send(embed=emb, view=view)
            else:
                await ctx.response.send_message(embed=emb, view=view)
                self.message = await ctx.original_response()
        except Exception:
            # Log and attempt a sanitized retry (remove image/thumbnail)
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

    # Buttons
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
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        try:
            if self.message:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except Exception:
            pass
