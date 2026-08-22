# mcoc/embeds.py
import typing

CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"


def _get_author_info(ctx_or_author):
    """
    Accept either a context-like object with .author or an author-like object.
    Return (display_name, avatar_url_or_none).
    """
    author = None
    if ctx_or_author is None:
        return ("Collector", None)
    # ctx passed
    if hasattr(ctx_or_author, "author"):
        author = ctx_or_author.author
    else:
        author = ctx_or_author
    name = getattr(author, "display_name", None) or getattr(author, "name", "Collector")
    # avatar may be a property or attribute; guard for None
    avatar = None
    try:
        av = getattr(author, "avatar", None)
        if av is not None:
            # discord.py v2: avatar may have .url; older libs may expose str()
            avatar = getattr(av, "url", None) or str(av)
    except Exception:
        avatar = None
    return (name, avatar)


async def cdt_embed(
    ctx_or_author=None,
    *,
    title: str = "",
    description: str = "",
    color=None,
    image: typing.Optional[str] = None,
    thumbnail: typing.Optional[str] = None,
    url: str = PATREON,
):
    """
    Build a standard CDT embed.
    ctx_or_author may be a Context (has .author) or an author-like object.
    This function lazily imports discord to avoid import-time dependency.
    """
    try:
        import discord
    except Exception:
        # If discord is not importable in this environment, return a simple dict-like fallback
        return {
            "title": title,
            "description": description,
            "color": color,
            "image": image,
            "thumbnail": thumbnail or CDT_LOGO,
            "url": url,
            "author": _get_author_info(ctx_or_author),
        }

    # Determine color
    if color is None:
        # try to use author's color if available
        author = getattr(ctx_or_author, "author", ctx_or_author)
        color = getattr(author, "color", None) or discord.Color.gold()

    embed = discord.Embed(title=title, description=description, color=color, url=url)

    # Author
    display_name, avatar_url = _get_author_info(ctx_or_author)
    if avatar_url:
        try:
            embed.set_author(name=display_name, icon_url=avatar_url)
        except Exception:
            embed.set_author(name=display_name)
    else:
        embed.set_author(name=display_name)

    # Images
    if image:
        try:
            embed.set_image(url=image)
        except Exception:
            pass

    embed.set_thumbnail(url=thumbnail or CDT_LOGO)

    try:
        embed.set_footer(
            text="Collector | Contest of Champions | CollectorDevTeam",
            icon_url=CDT_LOGO,
        )
    except Exception:
        # ignore footer failures
        pass

    return embed


async def champion_embed(ctx_or_author, champ: dict):
    desc = (
        f"Class: {champ.get('class','?').title()}\n"
        f"Tags: {', '.join(champ.get('tags', [])) or 'None'}"
    )

    embed = await cdt_embed(
        ctx_or_author,
        title=champ.get("name", "Unknown"),
        description=desc,
        thumbnail=(champ.get("images") or {}).get("portrait"),
    )

    # Abilities
    abilities = champ.get("abilities", []) or []
    if abilities:
        lines = []
        for a in abilities:
            t = a.get("type", "full")
            name = a.get("name", "?")
            lines.append(f"• {name} ({t})")
        try:
            embed.add_field(name="Abilities", value="\n".join(lines), inline=False)
        except Exception:
            pass

    # Immunities
    immunities = champ.get("immunities", []) or []
    if immunities:
        lines = []
        for i in immunities:
            t = i.get("type", "full")
            name = i.get("name", "?")
            note = i.get("note")
            if note:
                lines.append(f"• {name} ({t}) — {note}")
            else:
                lines.append(f"• {name} ({t})")
        try:
            embed.add_field(name="Immunities", value="\n".join(lines), inline=False)
        except Exception:
            pass

    return embed


async def abilities_embed(ctx_or_author, champ: dict):
    embed = await cdt_embed(
        ctx_or_author,
        title=f"{champ.get('name','Unknown')} — Abilities",
        thumbnail=(champ.get("images") or {}).get("portrait"),
    )

    for ability in champ.get("abilities", []) or []:
        name = ability.get("name", "?")
        t = ability.get("type", "full")
        note = ability.get("note")

        desc = f"Type: {t}"
        if note:
            desc += f"\nNote: {note}"

        try:
            embed.add_field(name=name, value=desc, inline=False)
        except Exception:
            pass

    return embed


async def synergy_embed(ctx_or_author, champ: dict, synergies: list):
    embed = await cdt_embed(
        ctx_or_author,
        title=f"{champ.get('name','Unknown')} — Synergies",
        thumbnail=(champ.get("images") or {}).get("portrait"),
    )

    for syn in synergies or []:
        name = syn.get("name", "?")
        desc = syn.get("description", "No description.")
        try:
            embed.add_field(name=name, value=desc, inline=False)
        except Exception:
            pass

    return embed


async def tag_list_embed(ctx_or_author, tag: str, champions: list):
    embed = await cdt_embed(
        ctx_or_author,
        title=f"Champions with #{tag}",
        description=f"{len(champions)} champions match this tag.",
    )

    lines = [c.get("name", "Unknown") for c in champions or []]
    try:
        embed.add_field(name="Matches", value="\n".join(lines) or "None", inline=False)
    except Exception:
        pass

    return embed


async def roster_entry_embed(ctx_or_author, champ: dict, entry: dict):
    """
    champ: champion object from cache
    entry: user roster entry dict
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

    embed = await cdt_embed(
        ctx_or_author,
        title=champ.get("name", "Unknown"),
        description=desc,
        thumbnail=(champ.get("images") or {}).get("portrait"),
    )

    return embed
