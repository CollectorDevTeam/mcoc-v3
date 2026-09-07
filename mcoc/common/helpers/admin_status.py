from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


def _count_present(champions: List[Dict[str, Any]], field: str) -> int:
    return len([champ for champ in champions if isinstance(champ, Mapping) and champ.get(field)])


def _truncate_version(value: Any, length: int = 12) -> str:
    text = str(value or "n/a")
    return text[:length]


async def collect_admin_status_snapshot(parent: Any, cache: Any, health_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = getattr(cache, "metadata", {}) or {}
    versions = meta.get("versions", {}) or {}
    champions = cache.get_all_champions() or []
    abilities = cache.get_all_abilities() or []
    tags = cache.get_all_tags() or []
    immunities = cache.get_all_immunities() or []
    aw_rows = cache.get_all_aw() or []
    champion_map_rows = cache.get_all_champions_map() or []
    glossary_rows = cache.get_all_glossary_terms() or []

    prestige_data = cache._load_file("prestige") or {}
    prestige_rows = prestige_data.get("rows", []) if isinstance(prestige_data, dict) else []

    tierlist_data = cache._load_file("tierlist") or {}
    tierlist_champions = tierlist_data.get("champions", []) if isinstance(tierlist_data, dict) else []
    tierlist_order = tierlist_data.get("tier_order", []) if isinstance(tierlist_data, dict) else []
    tierlist_tag_labels = tierlist_data.get("tag_labels", {}) if isinstance(tierlist_data, dict) else {}
    tierlist_immunity_types = tierlist_data.get("immunity_types", []) if isinstance(tierlist_data, dict) else []
    tierlist_debuff_types = tierlist_data.get("debuff_types", []) if isinstance(tierlist_data, dict) else []

    field_coverage = {
        "name": _count_present(champions, "name"),
        "class": _count_present(champions, "class") + _count_present(champions, "class_name"),
        "tags": _count_present(champions, "tags"),
        "abilities": _count_present(champions, "abilities"),
        "immunities": _count_present(champions, "immunities"),
        "inflicts": _count_present(champions, "inflicts"),
        "prestige": _count_present(champions, "prestige"),
        "synergies": _count_present(champions, "synergies"),
    }

    cocpit_probe: Dict[str, Any] = {
        "ok": False,
        "sample": None,
        "error": None,
        "sig_sections": 0,
        "core_sections": 0,
        "synergies": 0,
        "rotation_parts": 0,
        "base_stats": 0,
    }
    api = getattr(parent, "api", None)
    if api is not None and hasattr(api, "get_cocpit_champion_data") and champions:
        sample = next((champ for champ in champions if isinstance(champ, Mapping) and (champ.get("id") or champ.get("slug"))), None)
        if sample is not None:
            cocpit_probe["sample"] = sample.get("name") or sample.get("slug")
            try:
                rarity = int(sample.get("rarity") or sample.get("stars") or sample.get("tier") or 6)
            except Exception:
                rarity = 6
            try:
                rank = int(sample.get("rank") or 1)
            except Exception:
                rank = 1
            try:
                sig = int(sample.get("sig") or 0)
            except Exception:
                sig = 0
            try:
                asc = int(sample.get("ascended") or 0)
            except Exception:
                asc = 0
            try:
                payload = await api.get_cocpit_champion_data(str(sample.get("id") or sample.get("slug")), rarity, rank, sig, asc)
                if isinstance(payload, dict):
                    cocpit_probe["ok"] = True
                    cocpit_probe["sig_sections"] = len(payload.get("sigAbilities") or {}) if isinstance(payload.get("sigAbilities"), dict) else 0
                    cocpit_probe["core_sections"] = len(payload.get("coreAbilities") or {}) if isinstance(payload.get("coreAbilities"), dict) else 0
                    cocpit_probe["synergies"] = len(payload.get("synergies") or [])
                    cocpit_probe["rotation_parts"] = len((payload.get("rotationData") or {}).get("summary_parts") or []) if isinstance(payload.get("rotationData"), dict) else 0
                    cocpit_probe["base_stats"] = len(payload.get("baseStats") or {}) if isinstance(payload.get("baseStats"), dict) else 0
                else:
                    cocpit_probe["error"] = "empty or non-dict response"
            except Exception as exc:
                cocpit_probe["error"] = str(exc)

    return {
        "last_sync": meta.get("last_sync", "Never"),
        "versions": versions,
        "health_summary": health_summary or {"ok": True, "issues": [], "details": {}},
        "api_attached": bool(api),
        "champions": champions,
        "abilities": abilities,
        "tags": tags,
        "immunities": immunities,
        "aw_rows": aw_rows,
        "champion_map_rows": champion_map_rows,
        "glossary_rows": glossary_rows,
        "prestige_rows": prestige_rows,
        "tierlist_champions": tierlist_champions,
        "tierlist_order": tierlist_order,
        "tierlist_tag_labels": tierlist_tag_labels,
        "tierlist_immunity_types": tierlist_immunity_types,
        "tierlist_debuff_types": tierlist_debuff_types,
        "field_coverage": field_coverage,
        "cocpit_probe": cocpit_probe,
        "cocpit_url": getattr(api, "COCPIT_CHAMPION_URL", "https://cocpit.org/champion-abilities"),
    }


def build_admin_status_page_specs(snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    versions = snapshot.get("versions", {}) or {}
    health_summary = snapshot.get("health_summary", {}) or {}
    health_ok = bool(health_summary.get("ok", True))
    health_details_map = health_summary.get("details", {}) or {}
    champions = snapshot.get("champions", []) or []
    abilities = snapshot.get("abilities", []) or []
    tags = snapshot.get("tags", []) or []
    immunities = snapshot.get("immunities", []) or []
    aw_rows = snapshot.get("aw_rows", []) or []
    champion_map_rows = snapshot.get("champion_map_rows", []) or []
    glossary_rows = snapshot.get("glossary_rows", []) or []
    prestige_rows = snapshot.get("prestige_rows", []) or []
    tierlist_champions = snapshot.get("tierlist_champions", []) or []
    tierlist_order = snapshot.get("tierlist_order", []) or []
    tierlist_tag_labels = snapshot.get("tierlist_tag_labels", {}) or {}
    tierlist_immunity_types = snapshot.get("tierlist_immunity_types", []) or []
    tierlist_debuff_types = snapshot.get("tierlist_debuff_types", []) or []
    field_coverage = snapshot.get("field_coverage", {}) or {}
    cocpit_probe = snapshot.get("cocpit_probe", {}) or {}

    internal_lines = [
        f"Last sync: {snapshot.get('last_sync', 'Never')}",
        f"API attached: {'Yes' if snapshot.get('api_attached') else 'No'}",
        f"Cache health: {'Healthy' if health_ok else 'Issues detected'}",
        "",
        f"Champions: {len(champions)} ({'OK' if health_details_map.get('champions', {}).get('valid', True) else 'BAD'})",
        f"Abilities: {len(abilities)} ({'OK' if health_details_map.get('abilities', {}).get('valid', True) else 'BAD'})",
        f"Tags: {len(tags)} ({'OK' if health_details_map.get('tags', {}).get('valid', True) else 'BAD'})",
        f"Immunities: {len(immunities)} ({'OK' if health_details_map.get('immunities', {}).get('valid', True) else 'BAD'})",
        f"Champions Map: {len(champion_map_rows)}",
        f"Glossary: {len(glossary_rows)}",
        f"Prestige rows: {len(prestige_rows)}",
        "Export: ///mcocadmin export-champions",
    ]
    if not health_ok:
        issues = health_summary.get("issues", [])[:6]
        if issues:
            internal_lines.extend(["", "Health issues:", *[f"- {issue}" for issue in issues]])

    mcochub_lines = [
        "Primary sync source for champions, abilities, tags, immunities, and AW.",
        "",
        f"Champion rows: {len(champions)}",
        f"Ability rows: {len(abilities)}",
        f"Tag rows: {len(tags)}",
        f"Immunity rows: {len(immunities)}",
        f"AW payload rows: {len(aw_rows)}",
        f"Prestige rows: {len(prestige_rows)}",
        f"Version hashes: champions={_truncate_version(versions.get('champions'))} abilities={_truncate_version(versions.get('abilities'))} tags={_truncate_version(versions.get('tags'))} immunities={_truncate_version(versions.get('immunities'))}",
        "",
        "Coverage into CDT champion cache:",
        f"- abilities mapped on champions: {field_coverage.get('abilities', 0)}/{len(champions)}",
        f"- immunities mapped on champions: {field_coverage.get('immunities', 0)}/{len(champions)}",
        f"- inflicts mapped on champions: {field_coverage.get('inflicts', 0)}/{len(champions)}",
        f"- prestige mapped on champions: {field_coverage.get('prestige', 0)}/{len(champions)}",
    ]

    mcoc_app_lines = [
        "Tierlist/document source used for tier ordering and filter vocabulary metadata.",
        "",
        f"Tierlist champions: {len(tierlist_champions)}",
        f"Tier order entries: {len(tierlist_order)}",
        f"Tag labels: {len(tierlist_tag_labels) if isinstance(tierlist_tag_labels, dict) else 0}",
        f"Immunity types: {len(tierlist_immunity_types)}",
        f"Debuff types: {len(tierlist_debuff_types)}",
        f"Version hash: {_truncate_version(versions.get('tierlist'), 16)}",
        "",
        "Imported semantic fields:",
        "- champions[]",
        "- tag_labels",
        "- immunity_map / immunity_types",
        "- debuff_map / debuff_types",
        "- tier_order / tier_colors / class_colors",
    ]

    cocpit_lines = [
        "On-demand descriptive source for champion abilities and synergies.",
        "",
        f"Endpoint: {snapshot.get('cocpit_url')}",
        "Fetch mode: live per champion, not cached in the current cache manager",
        "",
        "Preferred detail fields:",
        "- sigAbilityDisplayName",
        "- sigAbilities",
        "- coreAbilities",
        "- synergies.title",
        "- synergies.description_parts",
        "- synergies.partners",
        "- rotationData.summary_parts",
        "- baseStats.Prestige",
        "",
        "Model status:",
        "- Cocpit champion detail model registered",
        "- Cocpit champion autocomplete model registered",
        "- champ abilities and synergies now prefer Cocpit text",
    ]

    if cocpit_probe.get("ok"):
        probe_lines = [
            f"Live Cocpit probe against sample champion: {cocpit_probe.get('sample')}",
            "",
            "Probe status: OK",
            f"Signature sections: {cocpit_probe.get('sig_sections', 0)}",
            f"Core sections: {cocpit_probe.get('core_sections', 0)}",
            f"Synergy cards: {cocpit_probe.get('synergies', 0)}",
            f"Rotation summary parts: {cocpit_probe.get('rotation_parts', 0)}",
            f"Base stat fields: {cocpit_probe.get('base_stats', 0)}",
        ]
    else:
        probe_lines = [
            f"Live Cocpit probe against sample champion: {cocpit_probe.get('sample') or 'Unavailable'}",
            "",
            "Probe status: FAILED",
            f"Error: {cocpit_probe.get('error') or 'No sample champion available'}",
            "",
            "This page confirms whether the live descriptive source is currently reachable.",
        ]

    rows = [
        ("name/id/slug", "champions.id,name", "champions.name/id", "champ_name input", "Champion.slug,name"),
        ("class", "champions.class", "champions.class", "className", "Champion.class_name"),
        ("abilities", "abilities + champ refs", "champion tags only", "coreAbilities,sigAbilities", "Champion.abilities"),
        ("immunities", "champions/immunities", "immunity_map,immunity_types", "embedded text only", "Champion.immunities"),
        ("inflicts", "derived from abilities", "debuff_map,debuff_types", "embedded text only", "Champion.inflicts"),
        ("synergies", "partial notes", "not modeled", "synergies.title/parts/partners", "detail helpers"),
        ("prestige", "prestige rows,map", "discarded from tierlist", "baseStats.Prestige", "Champion.prestige"),
    ]
    header = "Property         | MCOCHub              | mcoc.app                | Cocpit                    | CDT Internal"
    divider = "---------------- | -------------------- | ----------------------- | ------------------------- | --------------------"
    chart_lines = [header, divider]
    for prop, hub, app, cocpit, internal in rows:
        chart_lines.append(f"{prop:<16} | {hub:<20} | {app:<23} | {cocpit:<25} | {internal}")
    alignment_lines = [
        "```text",
        *chart_lines,
        "```",
        "Mapped field coverage:",
        f"- CDT champions with name: {field_coverage.get('name', 0)}/{len(champions)}",
        f"- CDT champions with class: {field_coverage.get('class', 0)}/{len(champions)}",
        f"- CDT champions with abilities: {field_coverage.get('abilities', 0)}/{len(champions)}",
        f"- CDT champions with immunities: {field_coverage.get('immunities', 0)}/{len(champions)}",
        f"- CDT champions with inflicts: {field_coverage.get('inflicts', 0)}/{len(champions)}",
        f"- mcoc.app metadata counts: tags={len(tierlist_tag_labels) if isinstance(tierlist_tag_labels, dict) else 0}, immunities={len(tierlist_immunity_types)}, debuffs={len(tierlist_debuff_types)}",
        f"- Cocpit live probe: sig={cocpit_probe.get('sig_sections', 0)} core={cocpit_probe.get('core_sections', 0)} synergies={cocpit_probe.get('synergies', 0)}",
    ]

    return [
        {"title": "MCOC Status | CDT Internal", "description": "\n".join(internal_lines)},
        {"title": "MCOC Status | MCOCHub", "description": "\n".join(mcochub_lines)},
        {"title": "MCOC Status | mcoc.app", "description": "\n".join(mcoc_app_lines)},
        {"title": "MCOC Status | Cocpit", "description": "\n".join(cocpit_lines)},
        {"title": "MCOC Status | Cocpit Probe", "description": "\n".join(probe_lines)},
        {"title": "MCOC Status | Property Alignment", "description": "\n".join(alignment_lines)},
    ]
