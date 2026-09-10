# Path: mcoc/common/models/cocpit/abilities.py
# File-Version: 1.0
# File-Id: 12345678-1234-1234-1234-1234567890ab
# Purpose: Pydantic models for champion abilities used by autocomplete endpoints
# Public-API: AbilityLine, CoreAbilityGroup, Synergy
# Internal: None
# Uses: typing, pydantic, re, unicodedata, hashlib
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
import re
import unicodedata
import hashlib

def slugify(text: str, max_len: int = 64) -> str:
    s = unicodedata.normalize("NFKD", text)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    if len(s) <= max_len:
        return s
    # keep prefix and append short hash for uniqueness
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]
    prefix = s[: max_len - 7].rstrip("-")
    return f"{prefix}-{h}"

class AbilityLine(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    iconFilename: Optional[str] = None
    text: Optional[str] = None

class CoreAbilityGroup(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    id: Optional[str] = None
    order: Optional[int] = None
    entries: List[AbilityLine] = Field(default_factory=list)
    raw_title: Optional[str] = None

    @model_validator(mode="before")
    def ensure_id_and_raw(cls, values):
        title = values.get("title") or values.get("raw_title") or ""
        champ_id = values.get("__champion_id")  # injected by loader
        if not values.get("id"):
            slug = slugify(title)
            if champ_id:
                values["id"] = f"{champ_id}__core__{slug}"
            else:
                values["id"] = f"core__{slug}"
        values["raw_title"] = title
        return values

class Synergy(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    id: Optional[str] = None
    description_parts: Optional[List[str]] = None
    partners: Optional[List[Dict[str, Any]]] = None
    raw_title: Optional[str] = None

    @model_validator(mode="before")
    def ensure_id_and_raw(cls, values):
        title = values.get("title") or ""
        champ_id = values.get("__champion_id")
        if not values.get("id"):
            slug = slugify(title)
            if champ_id:
                values["id"] = f"{champ_id}__synergy__{slug}"
            else:
                values["id"] = f"synergy__{slug}"
        values["raw_title"] = title
        return values
