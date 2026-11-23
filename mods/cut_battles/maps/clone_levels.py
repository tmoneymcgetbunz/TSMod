"""Wrapper levels for the three old late-game battle scripts (mods/cutbattles_proposal.md "Round 2").

The old scripts' own levels were never shipped. Each gets a copy of the shipped level its units fit [read: tile check
2026-11-22], under the old script's level name, with LuaScriptName pointed at the old script. An own level name means an
own GOP_Battle_Info row is found (the game reads the first row whose LevelName matches, Test 41c) [untested for a
renamed package].

What is renamed (UAssetGUI JSON):
- NameMap entries used only by the level itself: its package path, the level-script class `<lvl>_C` and its default
  object `Default__<lvl>_C` (replaced in place, so every use follows).
- The World export's ObjectName: a new name is added, because the old bare name is also the battle-grid import's object
  name (`WBAsset/<dir>/<lvl>`), which must stay.
- `LuaScriptName` on `Default__<lvl>_C`.

Input: the shipped umaps, extracted from the game pak into SRC (tools/tspak.py extract).
Output: maps/out/Newera/Map/Story/<dir>/<lvl>.umap/.uexp
Run: .venv/Scripts/python mods/cut_battles/maps/clone_levels.py
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
UAG = os.path.join(ROOT, "tools", "uassetgui", "UAssetGUI.exe")
SRC = os.path.join(HERE, "shipped")
# new level -> (new dir, shipped level, shipped dir, Lua script)
CLONES = {
    "ms19_x45_battle_02": ("ms19_x45", "ms19f_x45_battle_02", "ms19f_x45", "Scenario/Story/ms19_x45/ms19_x45_battle_02_old"),
    "ms21_x48_battle_01": ("ms21_x48", "ms21s_x48_battle_01", "ms21s_x48", "Scenario/Story/ms21_x48/ms21_x48_battle_01"),
    "ms21_x48_battle_02": ("ms21_x48", "ms21s_x48_battle_02", "ms21s_x48", "Scenario/Story/ms21_x48/ms21_x48_battle_02"),
}
ENV = dict(os.environ, DOTNET_ROLL_FORWARD="Major")


def uag(*args):
    r = subprocess.run([UAG, *args], env=ENV, capture_output=True, text=True, timeout=300)
    return r


def extract():
    import tspak, paths
    pak = tspak.Pak(os.path.join(paths.paks_dir(), "TRIANGLE_STRATEGY-WindowsNoEditor.pak"))
    for _, (_, old, odir, _) in CLONES.items():
        for ext in ("umap", "uexp"):
            k = f"TRIANGLE_STRATEGY/Content/Newera/Map/Story/{odir}/{old}.{ext}"
            dst = os.path.join(SRC, f"{old}.{ext}")
            os.makedirs(SRC, exist_ok=True)
            open(dst, "wb").write(pak.read(k))


def clone(new, ndir, old, odir, script):
    src = os.path.join(SRC, old + ".umap")
    js = os.path.join(SRC, old + ".json")
    if not os.path.exists(js):
        r = uag("tojson", src, js, "VER_UE4_27")
        assert os.path.exists(js), (r.stdout, r.stderr)
    d = json.load(open(js, encoding="utf-8"))
    nm = d["NameMap"]
    ren = {f"/Game/Newera/Map/Story/{odir}/{old}": f"/Game/Newera/Map/Story/{ndir}/{new}",
           f"{old}_C": f"{new}_C", f"Default__{old}_C": f"Default__{new}_C"}
    for a, b in ren.items():
        assert nm.count(a) == 1, (old, a)
        nm[nm.index(a)] = b
    nm.append(new)
    # Export names are stored as strings in the JSON and must match a NameMap entry: follow the class rename
    # (`<lvl>_C`, `Default__<lvl>_C`, and the level-script actor `<lvl>_C_1`, which is `<lvl>_C` with number 2).
    for e in d["Exports"]:
        for a, b in ren.items():
            if e["ObjectName"] == a or e["ObjectName"].startswith(a + "_") and e["ObjectName"][len(a) + 1:].isdigit():
                e["ObjectName"] = b + e["ObjectName"][len(a):]
    worlds =[e for e in d["Exports"] if e["ObjectName"] == old]
    assert len(worlds) == 1, (old, len(worlds))
    worlds[0]["ObjectName"] = new
    imps = [i for i in d["Imports"] if i["ObjectName"] == old]
    assert len(imps) == 1 and imps[0]["ClassName"] == "LevelWhiteBoxAsset", old   # the grid import keeps its name
    n = 0
    for e in d["Exports"]:
        for p in e.get("Data") or []:
            if p.get("Name") == "LuaScriptName":
                assert p["Value"] == f"Scenario/Story/{odir}/{old}", p["Value"]
                p["Value"] = script; n += 1
    assert n == 1, (old, n)
    # Every remaining mention of the old level name must be the grid import (path or object name).
    left = [s for s in nm if old in s]
    assert sorted(left) == sorted([old, f"/Game/Newera/Map/WBAsset/{odir}/{old}"]), left
    out_json = os.path.join(HERE, "out", new + ".json")
    out = os.path.join(HERE, "out", "Newera", "Map", "Story", ndir, new + ".umap")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(d, open(out_json, "w", encoding="utf-8"), indent=1)
    r = uag("fromjson", out_json, out)
    assert os.path.exists(out) and os.path.exists(out[:-5] + ".uexp"), (r.stdout, r.stderr)
    # Read back: the written file must parse to the same JSON.
    back = out_json[:-5] + ".check.json"
    uag("tojson", out, back, "VER_UE4_27")
    b = json.load(open(back, encoding="utf-8"))
    assert b["NameMap"] == d["NameMap"] and len(b["Exports"]) == len(d["Exports"]), new
    print(f"{new}: from {old}, script {script}, {os.path.getsize(out)}+{os.path.getsize(out[:-5] + '.uexp')} bytes")


def roundtrip_ok(old):
    """The unmodified shipped level must survive tojson/fromjson byte-identically."""
    js = os.path.join(SRC, old + ".json")
    if not os.path.exists(js):
        uag("tojson", os.path.join(SRC, old + ".umap"), js, "VER_UE4_27")
    rt = os.path.join(HERE, "rt", old + ".umap")
    os.makedirs(os.path.dirname(rt), exist_ok=True)
    uag("fromjson", js, rt)
    for ext in ("umap", "uexp"):
        a = open(os.path.join(SRC, f"{old}.{ext}"), "rb").read()
        b = open(rt[:-4] + ext, "rb").read()
        assert a == b, (old, ext, len(a), len(b))


if __name__ == "__main__":
    extract()
    for new, (ndir, old, odir, script) in CLONES.items():
        roundtrip_ok(old)
        clone(new, ndir, old, odir, script)
