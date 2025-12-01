import requests
import json

def load_ddragon_champion_map(patch: str):
    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json"
    data = requests.get(url).json()["data"]

    # main name → id
    name_to_id = {}

    for champ_id, info in data.items():
        pretty = info["name"].lower().replace(" ", "")
        raw_id = info["id"]    # correct DDragon filename
        name_to_id[pretty] = raw_id

        # also lowercase ID (kaisa, ksante, belveth)
        name_to_id[raw_id.lower()] = raw_id

    return name_to_id



def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def fuzzy_dd_lookup(raw: str, name_map: dict):
    key = raw.lower().replace(" ", "")

    # exact
    if key in name_map:
        return name_map[key]

    # substring
    for k in name_map:
        if key in k:
            return name_map[k]

    # fuzzy: pick best edit distance
    best = None
    best_dist = 999

    for k in name_map:
        dist = levenshtein(key, k)
        if dist < best_dist:
            best_dist = dist
            best = name_map[k]

    # accept only if reasonably close
    if best_dist <= 3:
        return best

    raise ValueError(f"No DDragon match for '{raw}'")
