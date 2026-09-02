# Path: mcoc/common/prefix_utils.py
# File-Version: 1.0
# File-Id: e95c98c8-ec36-4628-802f-74d5c4131c7b
# Purpose: Provide utility functions for handling command prefixes and safe message sending in MCOC bot context.
# Public-API: get_runtime_prefix, safe_send_ctx
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
from typing import Any, Optional
import logging
import asyncio
import inspect

log = logging.getLogger("red.mcoc.prefix_utils")

def get_runtime_prefix(ctx: Any, default: str = "///") -> str:
    """
    Return the prefix the user typed in this context, or a best-effort fallback.
    Prefer ctx.prefix (exact runtime prefix). If not available, try bot.command_prefix.
    """
    try:
        # Best: the prefix the user actually used in this invocation
        p = getattr(ctx, "prefix", None)
        if p:
            return p
    except Exception:
        pass

    try:
        bot = getattr(ctx, "bot", None)
        if not bot:
            return default
        cp = getattr(bot, "command_prefix", None)
        # If command_prefix is a callable, calling it requires a message; avoid calling here.
        if isinstance(cp, str):
            return cp
        if isinstance(cp, (list, tuple)) and cp:
            return cp[0]
    except Exception:
        pass

    return default


async def safe_send_ctx(ctx_or_channel: Any, content: Optional[str] = None, *, embed: Optional[Any] = None, view: Optional[Any] = None, ephemeral: bool = False) -> None:
    """
    Robust send helper.

    Uses inspect.iscoroutinefunction to detect coroutine-capable send targets.
    Falls back gracefully if the target doesn't support the expected API.
    """
    try:
        # Interaction-like (discord.Interaction)
        if hasattr(ctx_or_channel, "response") and getattr(ctx_or_channel, "response", None) is not None:
            try:
                if embed is not None:
                    await ctx_or_channel.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    await ctx_or_channel.response.send_message(content or "", view=view, ephemeral=ephemeral)
                return
            except Exception:
                # try followup
                try:
                    if embed is not None:
                        await ctx_or_channel.followup.send(embed=embed, view=view, ephemeral=ephemeral)
                    else:
                        await ctx_or_channel.followup.send(content or "", view=view, ephemeral=ephemeral)
                    return
                except Exception:
                    pass

        # Context or channel-like (commands.Context or discord.abc.Messageable)
        send_target = None
        if hasattr(ctx_or_channel, "send") and inspect.iscoroutinefunction(getattr(ctx_or_channel, "send")):
            send_target = ctx_or_channel
        else:
            ch = getattr(ctx_or_channel, "channel", None)
            if ch and hasattr(ch, "send") and inspect.iscoroutinefunction(getattr(ch, "send")):
                send_target = ch

        if send_target:
            if embed is not None:
                await send_target.send(embed=embed, view=view)
            else:
                await send_target.send(content or "")
            return

        # If ctx_or_channel.send exists but isn't a coroutine function (rare), try calling and awaiting if it returns a coroutine
        if hasattr(ctx_or_channel, "send"):
            try:
                maybe = ctx_or_channel.send(embed=embed if embed is not None else None, content=content or "")
                if asyncio.iscoroutine(maybe):
                    await maybe
                return
            except Exception:
                pass

        # Last resort: try channel attribute again
        ch = getattr(ctx_or_channel, "channel", None)
        if ch and hasattr(ch, "send"):
            try:
                maybe = ch.send(embed=embed if embed is not None else None, content=content or "")
                if asyncio.iscoroutine(maybe):
                    await maybe
                return
            except Exception:
                pass

        log.warning("safe_send_ctx: unable to send message; target=%r content=%r embed=%r", ctx_or_channel, content, bool(embed))
    except Exception:
        log.exception("safe_send_ctx failed for target=%r", ctx_or_channel)
