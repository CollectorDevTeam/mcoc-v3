def match_champion(champ, h):
    # rarity union
    if h["rarities"] and champ["rarity"] not in h["rarities"]:
        return False

    # rank union
    if h["ranks"] and champ["rank"] not in h["ranks"]:
        return False

    # sig union
    if h["sigs"] and champ["sig"] not in h["sigs"]:
        return False

    # class filter
    if h["classes"] and champ["class"].lower() not in h["classes"]:
        return False

    # tag intersection
    for tag in h["tags"]:
        if tag not in champ["tags"]:
            return False

    # negation
    for tag in h["not_tags"]:
        if tag in champ["tags"]:
            return False

    # champion name
    if h["champion"] and champ["slug"] != h["champion"]:
        return False

    return True
