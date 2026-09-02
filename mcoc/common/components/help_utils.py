# Path: mcoc/common/help_utils.py
# File-Version: 1.0
# File-Id: b1462bee-80e0-430f-baf0-efda265b0263
# Purpose: Provide utility functions for sending branded help messages in MCOC bot context.
# Public-API: send_or_brand_help
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
from typing import Optional
import logging
from redbot.core import commands
from .componentsV2 import CDTEmbed
from .prefix_utils import safe_send_ctx

log = logging.getLogger("red.mcoc.help")

async def send_or_brand_help(ctx: commands.Context, target: str, title: Optional[str] = None, fallback_text: Optional[str] = None):
    """
    Try to use Red's help system (ctx.send_help). If it returns a message with an embed,
    edit that embed to add CDT branding/footer. If send_help fails or returns plain text,
    send a CDTEmbed fallback built from the group's commands (use send_group_help if available).
    - target: the help target string (e.g., "account" or "mcoc account")
    - title: optional title to use when building fallback embed
    - fallback_text: optional fallback description
    """
    # 1) Try Red's help system first
    try:
        # ctx.send_help usually sends a message and returns it
        msg = await ctx.send_help(target)
        # If send_help returned a message and it has an embed, brand it
        if msg is not None:
            try:
                embeds = getattr(msg, "embeds", None)
                if embeds:
                    orig = embeds[0]
                    # Build a CDTEmbed that preserves fields/title/description
                    emb = CDTEmbed.embed(ctx,
                                         title=orig.title or (title or "Help"),
                                         description=orig.description or "",
                                         thumbnail=(orig.thumbnail.url if getattr(orig, "thumbnail", None) else None),
                                         image=(orig.image.url if getattr(orig, "image", None) else None,
                                                ) if False else None)  # we will copy fields below
                    # copy fields from original embed
                    try:
                        for f in getattr(orig, "fields", []):
                            try:
                                CDTEmbed.add_field(ctx, emb, name=f.name, value=f.value, inline=f.inline)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # copy url if present
                    try:
                        if getattr(orig, "url", None):
                            CDTEmbed.set_url(ctx, emb, orig.url)
                    except Exception:
                        pass
                    # set branded footer
                    try:
                        CDTEmbed.set_footer(ctx, emb, footer_text="Type `///help <command>` for more info")
                    except Exception:
                        pass
                    # edit the message to replace embed with branded one
                    try:
                        await msg.edit(embed=emb)
                        return msg
                    except Exception:
                        # If editing fails, just return the original message
                        log.debug("Failed to edit help message to branded embed", exc_info=True)
                        return msg
                else:
                    # send_help returned a text message (no embed) — fall through to fallback
                    pass
            except Exception:
                log.exception("Error while branding help message")
                return msg
    except Exception:
        # send_help may raise in some contexts (interactions, missing help command, etc.)
        log.debug("ctx.send_help failed or raised; falling back to CDTEmbed", exc_info=True)

    # 2) Fallback: build a CDTEmbed help card from fallback_text or title
    try:
        emb = CDTEmbed.embed(ctx, title=title or "Help", description=fallback_text or "Use ///help <command> for more details.")
        CDTEmbed.set_footer(ctx, emb, footer_text="Type ///help <command> for more info")
        await safe_send_ctx(ctx, None, embed=emb)
    except Exception:
        # final fallback: plain text
        await safe_send_ctx(ctx, fallback_text or "Help unavailable; try ///help <command>.")
    return None
