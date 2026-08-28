# mcoc/common/champions.py
"""
Champion helpers: deck-first champion search, filtering, formatting and page construction.

This module centralizes logic previously in prefix/champions.py and provides:
  - champion deck retrieval and safe cache access
  - filtering by name, tags, classes and hargs-like filters
  - formatting lines via format_champion_line
  - chunking results into branded CDTEmbed pages
  - convenience pager factory make_champion_pager

Prefix handlers should be thin: call make_champion_pager or get_champion_pages and start the pager.
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
import asyncio

from .formatters import format_champion_line
from .componentsV2 import CDTEmbed, CDTPagesMenu, CDT_FOOTER_TAG

log = logging.getLogger("red.mcoc.champions")


# -----------------------------
# Low-level cache helpers
# -----------------------------
def _get_all_champions_from_cache(core: Any) -> List[Dict[str, Any]]:
    """
    Safely retrieve the full champion deck from core.cache.
    Returns an empty list on any failure.
    """
    try:
        cache = getattr(core, "cache", None)
        if not cache:
            return []
        getter = getattr(cache, "get_all_champions", None) or getattr(cache, "all_champions", None)
        if callable(getter):
            return getter() or []
    except Exception:
        log.exception("Failed to retrieve champions from cache")
    return []

# -----------------------------
# Filtering helpers
# -----------------------------
def _champion_matches_filters(champ: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Return True if champion object matches the provided filters.
    Supported filters:
      - name: substring match against name or slug
      - tags: list of tag substrings (all must match)
      - classes: list of class names (any match)
    """
    try:
        if not filters:
            return True

        name_filter = (filters.get("name") or "").strip().lower() if filters.get("name") else None
        tag_filters = [t.lower() for t in (filters.get("tags") or [])]
        class_filters = [c.lower() for c in (filters.get("classes") or [])]

        # name/slug match
        if name_filter:
            name = (str(champ.get("name") or "") + " " + str(champ.get("slug") or "")).lower()
            if name_filter not in name:
                return False

        # class match
        if class_filters:
            champ_class = (champ.get("class") or "").lower()
            if champ_class not in class_filters:
                return False

        # tags: require all tag_filters to be present as substrings in at least one champ tag
        if tag_filters:
            champ_tags = [str(t).lower() for t in (champ.get("tags") or [])]
            for tf in tag_filters:
                ok = False
                for ct in champ_tags:
                    if tf in ct:
                        ok = True
                        break
                if not ok:
                    return False

        return True
    except Exception:
        return False

# -----------------------------
# Build champion lines and pages
# -----------------------------
def _format_champion_entry(champ: Dict[str, Any], default_entry: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a canonical entry dict for formatting and return a formatted line using format_champion_line.
    default_entry may supply rarity/rank/sig/ascended when the user provided explicit hargs.
    """
    try:
        entry = {
            "champion": champ.get("slug") or champ.get("id") or champ.get("name"),
            "rarity": int(default_entry.get("rarity")) if default_entry and default_entry.get("rarity") is not None else int(champ.get("stars") or champ.get("rarity") or 6),
            "rank": int(default_entry.get("rank")) if default_entry and default_entry.get("rank") is not None else 1,
            "sig": int(default_entry.get("sig")) if default_entry and default_entry.get("sig") is not None else 0,
            "ascended": int(default_entry.get("ascended")) if default_entry and default_entry.get("ascended") is not None else 0,
            "tags": default_entry.get("tags") if default_entry and default_entry.get("tags") is not None else (champ.get("tags") or []),
            "raw": champ.get("name") or champ.get("slug"),
        }
        # include class metadata for formatter
        if champ.get("class"):
            entry["class"] = champ.get("class")
        # call formatter (defensive about signature)
        try:
            return format_champion_line(champ, entry, include_prestige=None)
        except TypeError:
            return format_champion_line(champ, entry)
    except Exception:
        log.exception("Failed to format champion entry for %s", champ.get("slug") if champ else "<unknown>")
        # fallback simple line
        try:
            return f"**{champ.get('name') or champ.get('slug') or 'Unknown'}**"
        except Exception:
            return "Unknown"


async def build_champion_pages(core: Any, ctx_or_author: Any, filters: Optional[Dict[str, Any]] = None, *, lines_per_page: int = 15, char_limit: int = 1800) -> List[Any]:
    """
    Build a list of CDTEmbed pages for champion search results.

    Parameters:
      - core: bot/core object (used to access cache)
      - ctx_or_author: Context or author-like object used for branding (author name/avatar)
      - filters: dict from parse_query (name, tags, classes, raw_text)
      - lines_per_page, char_limit: pagination controls

    Returns:
      - List of CDTEmbed embed objects (normal path) or list of dict fallbacks on catastrophic failure.
    """
    # normalize author_for_embed
    author_for_embed = None
    try:
        if ctx_or_author is None:
            author_for_embed = None
        elif hasattr(ctx_or_author, "author"):
            author_for_embed = ctx_or_author.author
        else:
            author_for_embed = ctx_or_author
    except Exception:
        author_for_embed = None

    try:
        deck = _get_all_champions_from_cache(core)
        if not deck:
            # no champions available
            try:
                emb = CDTEmbed.embed(author_for_embed, title="Champions", description="No champion data available.", footer_text=f"Page 1 of 1{CDT_FOOTER_TAG}")
                return [emb]
            except Exception:
                return [{"title": "Champions", "description": "No champion data available.", "footer": {"text": f"Page 1 of 1{CDT_FOOTER_TAG}"}}]

        # apply deck-first filtering
        filt = filters or {}
        # If filters include explicit_entries (hargs tokens), prefer those champions (map slugs)
        explicit = filt.get("explicit_entries") if isinstance(filt, dict) else None

        matched: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []  # (champ_obj, default_entry)
        if explicit:
            # For each explicit entry, try to find matching champion in deck by slug or name
            slug_map = {}
            for c in deck:
                try:
                    slug_map[str(c.get("slug") or c.get("id") or "").lower()] = c
                    slug_map[str((c.get("name") or "").lower())] = c
                except Exception:
                    continue
            for ent in explicit:
                try:
                    key = str(ent.get("champion") or "").lower()
                    champ_obj = slug_map.get(key)
                    if not champ_obj:
                        # try contains/startswith fallback
                        for c in deck:
                            name = (c.get("name") or "").lower()
                            if key in name or name.startswith(key):
                                champ_obj = c
                                break
                    if champ_obj:
                        matched.append((champ_obj, ent))
                except Exception:
                    continue
        else:
            # No explicit entries: filter entire deck
            for c in deck:
                try:
                    if _champion_matches_filters(c, filt):
                        matched.append((c, None))
                except Exception:
                    continue

        if not matched:
            try:
                emb = CDTEmbed.embed(author_for_embed, title="Champions", description="No champions match your search.", footer_text=f"Page 1 of 1{CDT_FOOTER_TAG}")
                return [emb]
            except Exception:
                return [{"title": "Champions", "description": "No champions match your search.", "footer": {"text": f"Page 1 of 1{CDT_FOOTER_TAG}"}}]

        # Build formatted lines
        lines: List[str] = []
        for champ_obj, default_entry in matched:
            try:
                line = _format_champion_entry(champ_obj, default_entry)
                lines.append(line)
            except Exception:
                continue

        # Chunk into pages
        page_texts: List[str] = []
        cur: List[str] = []
        cur_len = 0
        for line in lines:
            if len(cur) >= lines_per_page or (cur_len + len(line) + 1) > char_limit:
                page_texts.append("\n".join(cur))
                cur = []
                cur_len = 0
            cur.append(line)
            cur_len += len(line) + 1
        if cur:
            page_texts.append("\n".join(cur))

        # Build title and embeds
        title = f"Champions ({len(matched)})"
        embed_pages: List[Any] = []
        try:
            for i, ptext in enumerate(page_texts):
                footer = f"Page {i+1} of {len(page_texts)}{CDT_FOOTER_TAG}"
                emb = CDTEmbed.embed(author_for_embed, title=title, description=ptext, footer_text=footer)
                try:
                    emb.set_footer(text=footer)
                except Exception:
                    pass
                embed_pages.append(emb)
            return embed_pages
        except Exception:
            out = []
            for i, ptext in enumerate(page_texts):
                out.append({"title": title, "description": ptext, "footer": {"text": f"Page {i+1} of {len(page_texts)}{CDT_FOOTER_TAG}"}})
            return out

    except Exception:
        log.exception("Failed to build champion pages")
        return []


async def get_champion_pages(core: Any, ctx_or_author: Any, filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Public wrapper that returns embed pages for champion search results.
    Guarantees embed objects where possible.
    """
    pages = await build_champion_pages(core, ctx_or_author, filters=filters)
    out: List[Any] = []
    for p in pages:
        if isinstance(p, dict):
            try:
                emb = CDTEmbed.embed(ctx_or_author, title=p.get("title"), description=p.get("description"), footer_text=(p.get("footer") or {}).get("text"))
                out.append(emb)
            except Exception:
                out.append(p)
        else:
            out.append(p)
    return out


async def make_champion_pager(core: Any, ctx_or_author: Any, *, raw_input: Optional[str] = None, parsed_filters: Optional[Dict[str, Any]] = None, author_for_controls: Optional[Any] = None) -> Optional[CDTPagesMenu]:
    """
    Convenience wrapper that builds champion pages and returns a ready CDTPagesMenu with brand buttons merged.

    Parameters:
      - core: bot/core object
      - ctx_or_author: Context or author-like object (used for branding)
      - raw_input: optional raw input string (if parsed_filters not provided)
      - parsed_filters: optional filters dict (preferred)
      - author_for_controls: who should control the pager (defaults to ctx_or_author.author or ctx_or_author)

    Returns:
      - CDTPagesMenu instance ready to start, or None on failure.
    """
    try:
        parsed = parsed_filters or {}
        if not parsed and raw_input:
            try:
                # lazy import to avoid circulars
                from .query_parser import parse_query
                cache = getattr(core, "cache", None)
                entries, filters = parse_query(raw_input, cache=cache)
                parsed = {}
                if entries:
                    parsed["explicit_entries"] = entries
                if isinstance(filters, dict):
                    parsed.update(filters)
            except Exception:
                parsed = {}

        pages = await get_champion_pages(core, ctx_or_author, filters=parsed)
        if not pages:
            return None

        # Instantiate pager
        try:
            pager = CDTPagesMenu(pages, author=(author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author)))
        except TypeError:
            try:
                pager = CDTPagesMenu(pages, ctx_or_author)
            except TypeError:
                try:
                    pager = CDTPagesMenu(pages)
                    if hasattr(pager, "author"):
                        try:
                            pager.author = (author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author))
                        except Exception:
                            pass
                except Exception:
                    return None

        # Merge brand buttons if available
        try:
            brand_view = CDTEmbed.brand_view()
            if hasattr(pager, "add_item"):
                for item in getattr(brand_view, "children", []):
                    try:
                        pager.add_item(item)
                    except Exception:
                        continue
        except Exception:
            pass

        return pager
    except Exception:
        log.exception("make_champion_pager failed")
        return None


# -----------------------------
# Footer helper (reusable)
# -----------------------------
def add_page_footers(pages: List[Any], author_for_embed: Any = None) -> List[Any]:
    """
    Ensure each embed page has a footer with page numbering.
    Accepts embed objects or dict fallbacks.
    """
    out: List[Any] = []
    total = len(pages)
    for i, p in enumerate(pages):
        try:
            if isinstance(p, dict):
                emb = CDTEmbed.embed(author_for_embed, title=p.get("title", "Champions"), description=p.get("description", ""))
            else:
                emb = p
            try:
                base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
                footer_text = f"{base} • Page {i+1} of {total}" if base else f"Page {i+1} of {total}"
                footer_text += f"{CDT_FOOTER_TAG}"
                emb.set_footer(text=footer_text)
            except Exception:
                try:
                    emb.set_footer(text=f"Page {i+1} of {total}{CDT_FOOTER_TAG}")
                except Exception:
                    pass
            out.append(emb)
        except Exception:
            out.append(p)
    return out
