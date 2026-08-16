import discord

CDT_LOGO = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png"
CDT_ICON = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png"
PATREON = "https://patreon.com/collectorbot"

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
