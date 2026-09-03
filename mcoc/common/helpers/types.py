# Path: mcoc/common/helpers/types.py
# File-Version: 1.0
# File-Id: 0166f08d-8249-4c90-a6de-7e4116ed52d9
# Purpose: Define core types and dataclasses for MCOC entities (Champion, UserAccount).
# Public-API: Champion, champion_from_dict, UserAccount
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
from dataclasses import dataclass, field, asdict
import datetime
import logging
from typing import Any, Dict, List, Optional, Mapping, TypedDict, Union

log = logging.getLogger("red.mcoc.types")


@dataclass
class Champion:
    """Runtime model for champion metadata (lightweight, tolerant)."""
    slug: str
    name: Optional[str] = None
    class_name: Optional[str] = None
    tier: Optional[int] = None
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
        # tier/rarity alias is commonly exposed as stars or rarity in cached data
        tier = d.get("tier") or d.get("stars") or d.get("rarity")
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
            tier=int(tier) if isinstance(tier, (int, str)) and str(tier).strip().isdigit() else None,
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


@dataclass
class UserAccount:
    """
    Dataclass representing the user's account/profile metadata.

    This is the shape used by account helpers and persisted profile fields.
    """
    user_id: int
    mcoc_name: Optional[str] = None
    mcoc_id: Optional[str] = None
    display_name: Optional[str] = None
    website: Optional[str] = None
    invite: Optional[str] = None
    timezone: Optional[str] = None
    alliance: Optional[str] = None
    job: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    about: Optional[str] = None
    mastery: Optional[str] = None
    started: Optional[str] = None        # normalized ISO date YYYY-MM-DD when available
    roster_public: bool = False
    privacy_mode: Optional[str] = None
    linked: bool = False
    prestige_map: Dict[str, int] = field(default_factory=dict)
    top5: List[str] = field(default_factory=list)

    # Consent metadata
    consent: bool = False
    consent_ts: Optional[str] = None     # ISO date YYYY-MM-DD or full ISO
    consent_version: Optional[str] = None
    consent_source: Optional[str] = None

    # Internal / audit
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a plain dict suitable for JSON storage.
        """
        return asdict(self)

    @classmethod
    def _normalize_started(cls, value: Optional[str]) -> Optional[str]:
        """
        Lightweight normalization for 'started' values.
        Attempts to return YYYY-MM-DD or None.
        This is intentionally conservative; more advanced heuristics live in account helpers.
        """
        if not value:
            return None
        s = str(value).strip()
        # try ISO date first
        try:
            if len(s) == 10 and s.count("-") == 2:
                # date-only ISO
                datetime.date.fromisoformat(s)
                return s
            # try full ISO parse
            dt = datetime.datetime.fromisoformat(s)
            return dt.date().isoformat()
        except Exception:
            pass
        # try common US numeric formats MM/DD/YYYY or MM-DD-YYYY
        try:
            for sep in ("/", "-"):
                parts = s.split(sep)
                if len(parts) == 3:
                    mm, dd, yy = parts
                    mm_i = int(mm); dd_i = int(dd); yy_i = int(yy)
                    if yy_i < 100:  # two-digit year heuristic
                        yy_i = 2000 + yy_i if yy_i <= 29 else 1900 + yy_i
                    dt = datetime.date(yy_i, mm_i, dd_i)
                    return dt.isoformat()
        except Exception:
            pass
        # fallback: return None (leave raw value in storage if caller prefers)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserAccount":
        """
        Construct a UserAccount from a dict (storage). Defensive: ignore unknown keys.
        Normalizes a few common fields (booleans, started).
        """
        if not isinstance(data, dict):
            raise TypeError("from_dict expects a dict")

        # gather known fields with safe defaults
        kwargs: Dict[str, Any] = {}
        fields = {
            "user_id", "mcoc_name", "mcoc_id", "display_name", "website", "invite",
            "timezone", "alliance", "job", "age", "gender", "about", "mastery",
            "started", "roster_public", "privacy_mode", "linked", "prestige_map",
            "top5", "consent", "consent_ts", "consent_version", "consent_source",
            "created_at", "updated_at"
        }

        for k in fields:
            if k in data:
                kwargs[k] = data.get(k)

        # ensure user_id exists and is int
        uid = kwargs.get("user_id") or data.get("user_id") or 0
        try:
            kwargs["user_id"] = int(uid)
        except Exception:
            kwargs["user_id"] = 0

        # coerce booleans
        kwargs["roster_public"] = bool(kwargs.get("roster_public", False))
        kwargs["linked"] = bool(kwargs.get("linked", False))
        kwargs["consent"] = bool(kwargs.get("consent", False))

        # ensure prestige_map is a dict
        pm = kwargs.get("prestige_map") or {}
        if not isinstance(pm, dict):
            try:
                pm = dict(pm)
            except Exception:
                pm = {}
        # coerce values to int where possible
        clean_pm: Dict[str, int] = {}
        for k, v in pm.items():
            try:
                clean_pm[k] = int(v) if v is not None else 0
            except Exception:
                clean_pm[k] = 0
        kwargs["prestige_map"] = clean_pm

        # ensure top5 is a list of strings
        t5 = kwargs.get("top5") or []
        if not isinstance(t5, list):
            try:
                t5 = list(t5)
            except Exception:
                t5 = []
        kwargs["top5"] = [str(x) for x in t5]

        # normalize started to ISO date when possible (conservative)
        started_raw = kwargs.get("started")
        normalized = cls._normalize_started(started_raw) if started_raw else None
        if normalized:
            kwargs["started"] = normalized
        else:
            # keep raw string if present but not normalized (so callers can decide)
            kwargs["started"] = started_raw

        # created_at / updated_at: keep as-is (caller may set)
        return cls(**kwargs)


# -----------------------------
# Types describing on-disk user data (UserDataManager shape)
# -----------------------------
class UserDataProfile(TypedDict, total=False):
    mcoc_id: Optional[str]
    mcoc_name: Optional[str]
    consent: Optional[bool]
    consent_ts: Optional[str]
    consent_version: Optional[str]
    consent_source: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    prestige_map: Dict[str, Any]


class UserData(TypedDict):
    user_id: str
    roster: List[Dict[str, Any]]
    profile: UserDataProfile
    privacy: Dict[str, Any]
    alliances: Dict[str, str]


# Convenience helpers for interop between UserData (storage) and UserAccount (dataclass)
def useraccount_from_userdata(data: Union[UserData, Dict[str, Any]]) -> UserAccount:
    """
    Convert a raw UserData/profile dict into a UserAccount dataclass.
    """
    if not isinstance(data, dict):
        raise TypeError("useraccount_from_userdata expects a dict-like UserData")
    profile = data.get("profile") if "profile" in data else data
    if not isinstance(profile, dict):
        profile = {}
    # ensure user_id is present at top-level or in profile
    uid = data.get("user_id") or profile.get("user_id") or profile.get("user_id")
    if uid is None:
        uid = 0
    # merge top-level profile keys into a single dict for from_dict
    merged = dict(profile)
    merged["user_id"] = uid
    return UserAccount.from_dict(merged)


def userdata_from_useraccount(account: UserAccount) -> UserData:
    """
    Convert a UserAccount dataclass into the on-disk UserData shape (minimal).
    Note: this produces a minimal UserData dict suitable for saving under the
    'profile' key of the UserDataManager file.
    """
    profile = account.to_dict()
    return {
        "user_id": str(account.user_id),
        "roster": [],
        "profile": profile,
        "privacy": {"mode": "private"},
        "alliances": {},
    }
