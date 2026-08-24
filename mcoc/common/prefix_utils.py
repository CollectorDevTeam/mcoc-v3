# mcoc/common/prefix_utils.py
from typing import Any

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
