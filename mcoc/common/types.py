# mcoc/common/types.py
from dataclasses import dataclass
import logging

log = logging.getLogger("red.mcoc.types")
from typing import Any, Dict, List, Optional, Mapping

@dataclass
class Champion:
    """Runtime model for champion metadata (lightweight, tolerant)."""
    slug: str
    name: Optional[str] = None
    class_name: Optional[str] = None
    images: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    abilities: Optional[List[Dict[str, Any]]] = None
    immunities: Optional[List[Dict[str, Any]]] = None
    release_year: Optional[int] = None
    raw: Optional[Mapping[str, Any]] = None

    @property
    def class_lower(self) -> str:
        return (self.class_name or "").lower()

    def get_portrait(self) -> Optional[str]:
        # prefer explicit images dict, then image_url, then raw fallbacks
        if self.images:
            # common keys: portrait, image, thumbnail
            for k in ("portrait", "image", "thumbnail"):
                if k in self.images and self.images[k]:
                    return self.images[k]
        if self.image_url:
            return self.image_url
        if self.raw and isinstance(self.raw, Mapping):
            return self.raw.get("image_url") or self.raw.get("image")
        return None


def champion_from_dict(d: Optional[Mapping[str, Any]]) -> Optional[Champion]:
    """
    Convert a champion-like dict (MCOCHub or other source) into Champion dataclass.
    Tolerant mapping: accepts keys like 'id'|'slug', 'name', 'class', 'image_url', 'images', 'tags'.
    """
    if not d:
        return None
    try:
        # slug/id normalization
        slug = d.get("id") or d.get("slug") or (d.get("name") and str(d.get("name")).lower().replace(" ", "-"))
        if slug is None:
            return None
        name = d.get("name") or d.get("title") or str(slug)
        # class may be 'class' key in MCOCHub
        class_name = d.get("class") or d.get("class_name") or d.get("class_")
        # images: MCOCHub uses image_url; other sources may provide images dict
        images = None
        if isinstance(d.get("images"), dict):
            images = d.get("images")
        elif d.get("image_url"):
            images = {"portrait": d.get("image_url")}
        image_url = d.get("image_url") or (images.get("portrait") if images else None)
        tags = d.get("tags") or d.get("keywords") or None
        abilities = d.get("abilities") or None
        immunities = d.get("immunities") or None
        release_year = d.get("release_year") or None

        return Champion(
            slug=str(slug),
            name=name,
            class_name=class_name,
            images=images,
            image_url=image_url,
            tags=tags,
            abilities=abilities,
            immunities=immunities,
            release_year=release_year,
            raw=d,
        )
    except Exception:
        log.exception("Failed to create Champion from dict: %s", d)
        return None
