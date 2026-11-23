"""Remove the WorldMapLevel sublevel from the three cut battle levels that hang on the loading screen (Test 41b).

Test 41b [tested]: the Tourney, river and Roselle drafts load their Lua script but never reach battle setup. They are the
only battle levels that stream /Game/Newera/Map/Common/WorldMapLevel (no shipped battle level does; an old Chapter 1
test level is the only other one) [read: all 56 battle .umap files]. Cause [inferred]: the world map level.

The World export's serialized data (UAssetGUI "Extras") is: int32 PersistentLevel, int32 0, then the StreamingLevels
TArray (int32 count + export indices). We drop the WorldMapLevel streaming object from that array and from the World's
create-before-serialization dependencies; the orphaned streaming object stays in the file but is never streamed.

Input:  maps/src/<level>.json (UAssetGUI tojson of the vanilla level, round-trip verified byte-identical)
Output: maps/out/Newera/Map/Story/<dir>/<level>.umap/.uexp (UAssetGUI fromjson)
Run: .venv/Scripts/python mods/cut_battles/maps/fix_levels.py

Roselle draft (ms12_x23_battle_01, user decision 2026-11-21: use the real village map; roselle_map_diff.md): instead of
dropping WorldMapLevel, its streaming slot is repointed to the village art, the SkySetLevel_Dummy slot to the village
props, the developer whitebox to the shipped village terrain, and the battle-grid import to the shipped Chapter 11 grid
(WBAsset/ms11_x20/ms11_x20_battle_01). All draft unit and deployment positions are valid tiles there [read].
New names are appended to the name map (old ones stay; e.g. "ms12_x23_battle_01" is also the level's own name).
"""
import base64, json, os, struct, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UAG = os.path.join(ROOT, "tools", "uassetgui", "UAssetGUI.exe")
LEVELS = {"ms02_x02_battle_02": "ms02_x02", "ms14_x29_battle_02": "ms14_x29", "ms12_x23_battle_01": "ms12_x23"}
V = "/Game/Newera/Map/Common/A1/A1_EX_Village/"
REPOINT = {  # level -> {old sublevel asset name: new}, and the grid swap
    "ms12_x23_battle_01": {
        "sublevels": {
            V + "A1_EX_Villagesano_WB.A1_EX_Villagesano_WB": V + "A1_EX_Village_WB.A1_EX_Village_WB",
            "/Game/Newera/Map/Common/WorldMapLevel.WorldMapLevel": V + "A1_EX_Village_GFX.A1_EX_Village_GFX",
            "/Game/Newera/Map/Common/SkySetLevel_Dummy.SkySetLevel_Dummy": V + "A1_EX_Village_B_OTH.A1_EX_Village_B_OTH",
        },
        "grid": ("/Game/Newera/Map/WBAsset/ms11_x20/ms11_x20_battle_01", "ms11_x20_battle_01"),
    },
}
DROP = "WorldMapLevel"


def world_asset(e):
    for p in e.get("Data", []):
        if p.get("Name") == "WorldAsset":
            return p["Value"]["AssetPath"]["AssetName"] or ""
    return ""


def add_name(d, n):
    if n not in d["NameMap"]:
        d["NameMap"].append(n)


def repoint(d, cfg):
    done = []
    for e in d["Exports"]:
        for p in e.get("Data", []):
            if p.get("Name") == "WorldAsset":
                ap = p["Value"]["AssetPath"]
                new = cfg["sublevels"].get(ap["AssetName"])
                if new:
                    add_name(d, new); add_name(d, new.split(".")[0])
                    done.append((e["ObjectName"], ap["AssetName"].split("/")[-1], new.split("/")[-1]))
                    ap["AssetName"] = new
    assert len(done) == len(cfg["sublevels"]), done
    pkg, obj = cfg["grid"]
    imps = d["Imports"]
    wb = [i for i, im in enumerate(imps) if im["ClassName"] == "LevelWhiteBoxAsset"]
    assert len(wb) == 1
    owner = imps[-imps[wb[0]]["OuterIndex"] - 1]
    assert owner["ClassName"] == "Package" and "/WBAsset/" in owner["ObjectName"]
    add_name(d, pkg); add_name(d, obj)
    done.append(("grid", owner["ObjectName"], pkg))
    owner["ObjectName"] = pkg
    imps[wb[0]]["ObjectName"] = obj
    for x in done: print("   repoint", x)


def fix(level, folder):
    d = json.load(open(os.path.join(HERE, "src", level + ".json"), encoding="utf-8"))
    ex = d["Exports"]
    if level in REPOINT:
        repoint(d, REPOINT[level])
        return write(d, level, folder)
    drop = [i for i, e in enumerate(ex, 1) if e["ObjectName"].startswith("LevelStreaming") and DROP in world_asset(e)]
    assert len(drop) == 1, (level, drop)
    k = drop[0]
    worlds = [e for e in ex if e["ObjectName"] == level and e.get("Extras")]
    assert len(worlds) == 1, level
    w = worlds[0]
    raw = base64.b64decode(w["Extras"])
    vals = list(struct.unpack("<%di" % (len(raw) // 4), raw))
    persistent, zero, count, items = vals[0], vals[1], vals[2], vals[3:]
    assert zero == 0 and count == len(items) and k in items, (level, vals)
    items = [i for i in items if i != k]
    w["Extras"] = base64.b64encode(struct.pack("<%di" % (3 + len(items)), persistent, 0, len(items), *items)).decode()
    w["CreateBeforeSerializationDependencies"] = [i for i in w["CreateBeforeSerializationDependencies"] if i != k]
    print(f"{level}: streaming levels {count} -> {len(items)} (dropped export {k}, {ex[k-1]['ObjectName']})")
    return write(d, level, folder)


def write(d, level, folder):
    out_json = os.path.join(HERE, "out", level + ".json")
    out_asset = os.path.join(HERE, "out", "Newera", "Map", "Story", folder, level + ".umap")
    os.makedirs(os.path.dirname(out_asset), exist_ok=True)
    json.dump(d, open(out_json, "w", encoding="utf-8"), indent=1)
    env = dict(os.environ, DOTNET_ROLL_FORWARD="Major")
    r = subprocess.run([UAG, "fromjson", out_json, out_asset], env=env, capture_output=True, text=True, timeout=300)
    assert os.path.exists(out_asset) and os.path.exists(out_asset[:-5] + ".uexp"), (r.stdout, r.stderr)
    return out_asset


if __name__ == "__main__":
    for lv, fo in LEVELS.items():
        print("  ->", fix(lv, fo))
