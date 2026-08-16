import discord

CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"

# ---------------------------------------------------------
# Base CDT Embed
# ---------------------------------------------------------
async def cdt_embed(
    ctx,
    *,
    title="",
    description="",
    color=None,
    image=None,
    thumbnail=None,
    url=PATREON,
):
    color = color or getattr(ctx.author, "color", discord.Color.gold())
    embed = discord.Embed(title=title, description=description, color=color, url=url)

    # Author
    if hasattr(ctx.author.avatar, "url"):
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
    else:
        embed.set_author(name=ctx.author.display_name)

    # Images
    if image:
        embed.set_image(url=image)

    embed.set_thumbnail(url=thumbnail or CDT_LOGO)

    embed.set_footer(
        text="Collector | Contest of Champions | CollectorDevTeam",
        icon_url=CDT_LOGO
    )

    return embed


# ---------------------------------------------------------
# Champion Info Embed
# ---------------------------------------------------------
async def champion_embed(ctx, champ):
    desc = (
        f"Class: {champ.get('class','?').title()}\n"
        f"Tags: {', '.join(champ.get('tags', [])) or 'None'}"
    )

    embed = await cdt_embed(
        ctx,
        title=champ["name"],
        description=desc,
        thumbnail=champ.get("images", {}).get("portrait")
    )

    # Abilities
    abilities = champ.get("abilities", [])
    if abilities:
        lines = []
        for a in abilities:
            t = a.get("type", "full")
            name = a.get("name", "?")
            lines.append(f"• {name} ({t})")
        embed.add_field(name="Abilities", value="\n".join(lines), inline=False)

    # Immunities
    immunities = champ.get("immunities", [])
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
        embed.add_field(name="Immunities", value="\n".join(lines), inline=False)

    return embed


# ---------------------------------------------------------
# Abilities Embed
# ---------------------------------------------------------
async def abilities_embed(ctx, champ):
    embed = await cdt_embed(
        ctx,
        title=f"{champ['name']} — Abilities",
        thumbnail=champ.get("images", {}).get("portrait")
    )

    for ability in champ.get("abilities", []):
        name = ability.get("name", "?")
        t = ability.get("type", "full")
        note = ability.get("note")

        desc = f"Type: {t}"
        if note:
            desc += f"\nNote: {note}"

        embed.add_field(name=name, value=desc, inline=False)

    return embed


# ---------------------------------------------------------
# Synergy Embed
# ---------------------------------------------------------
async def synergy_embed(ctx, champ, synergies):
    embed = await cdt_embed(
        ctx,
        title=f"{champ['name']} — Synergies",
        thumbnail=champ.get("images", {}).get("portrait")
    )

    for syn in synergies:
        name = syn.get("name", "?")
        desc = syn.get("description", "No description.")
        embed.add_field(name=name, value=desc, inline=False)

    return embed


# ---------------------------------------------------------
# Tag List Embed
# ---------------------------------------------------------
async def tag_list_embed(ctx, tag, champions):
    embed = await cdt_embed(
        ctx,
        title=f"Champions with #{tag}",
        description=f"{len(champions)} champions match this tag."
    )

    lines = [c["name"] for c in champions]
    embed.add_field(name="Matches", value="\n".join(lines), inline=False)

    return embed

# ---------------------------------------------------------
# Roster Entry Embed
# ---------------------------------------------------------
async def roster_entry_embed(ctx, champ, entry):
    """
    champ: champion object from cache
    entry: user roster entry dict
    """
    rarity = entry.get("rarity", "?")
    rank = entry.get("rank", "?")
    sig = entry.get("sig", "?")
    tags = entry.get("tags", [])

    desc = (
        f"Rarity: {rarity}★\n"
        f"Rank: {rank}\n"
        f"Signature: {sig}\n"
        f"Tags: {', '.join(tags) if tags else 'None'}"
    )

    embed = await cdt_embed(
        ctx,
        title=champ["name"],
        description=desc,
        thumbnail=champ.get("images", {}).get("portrait")
    )

    return embed
