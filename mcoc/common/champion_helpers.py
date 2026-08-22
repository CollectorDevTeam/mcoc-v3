# mcoc/common/helpers.py

from typing import Any, Optional, List, Dict

# Champion resolution -------------------------------------------------------
def resolve_champion(cache, key: str) -> Optional[Dict]:
    """Resolve by id, slug, or case-insensitive name. Returns champion dict or None."""
    if not cache:
        return None
    try:
        # prefer cache API
        c = cache.get_champion(key)
        if c:
            return c
    except Exception:
        pass
    # fallback scan
    try:
        for champ in cache.get_all_champions() or []:
            if str(champ.get("id") or champ.get("slug") or "").lower() == str(key).lower():
                return champ
            if str(champ.get("name") or "").lower() == str(key).lower():
                return champ
    except Exception:
        return None
    return None

# Safe send helpers ---------------------------------------------------------
async def safe_send_ctx(ctx, content=None, embed=None, file=None):
    """Send in prefix context with fallbacks; swallow non-fatal errors."""
    try:
        return await ctx.send(content=content, embed=embed, file=file)
    except Exception:
        try:
            if embed is not None:
                return await ctx.send(embed=embed)
            if content is not None:
                return await ctx.send(content)
        except Exception:
            return None

async def safe_respond_interaction(interaction, *, content=None, embed=None, ephemeral=False, followup=False):
    """Respond to an interaction safely; use followup if already responded."""
    try:
        if followup:
            return await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        return await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
    except Exception:
        try:
            # fallback to followup
            return await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        except Exception:
            return None

# Stat utilities ------------------------------------------------------------
def lookup_stat(champ: Dict, rarity: int, rank: int, ascended: int = 0) -> Optional[Dict]:
    """Return statline dict or None. Handles ascension keys like '3A1'."""
    stats = champ.get("stats") or {}
    rarity_table = stats.get(str(rarity)) or {}
    key = str(rank)
    if ascended and isinstance(ascended, int) and ascended > 0:
        asc_key = f"{rank}A{ascended}"
        if asc_key in rarity_table:
            key = asc_key
    return rarity_table.get(key)

# Pagination helper ---------------------------------------------------------
def add_page_footers(pages: List[Any]) -> List[Any]:
    """Add 'Page X of Y' footer to embed-like objects (discord.Embed or dict fallback)."""
    total = len(pages)
    out = []
    for i, e in enumerate(pages):
        try:
            import discord
            if isinstance(e, discord.Embed):
                try:
                    e.set_footer(text=f"Page {i+1} of {total}")
                except Exception:
                    pass
                out.append(e)
                continue
        except Exception:
            pass
        # dict fallback
        if isinstance(e, dict):
            f = e.get("footer", {}) or {}
            text = f.get("text", "")
            text = f"{text} | Page {i+1} of {total}" if text else f"Page {i+1} of {total}"
            e["footer"] = {"text": text, "icon_url": f.get("icon_url")}
        out.append(e)
    return out
