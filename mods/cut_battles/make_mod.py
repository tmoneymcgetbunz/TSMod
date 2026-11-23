"""Generate mods/cut_battles/mod.json: the six cut story battles in the story-battle picker.

Decisions (user, 2026-11-20): all six, always available, enemy levels like shipped replays (by New Game+ count),
rewards copied from the neighbouring shipped battle, English text, titles "(Cut Content) ...".
Proposal: mods/cutbattles_proposal.md. Run: .venv/Scripts/python mods/cut_battles/make_mod.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
QI = "Newera/Data/DataTables/GOP_Quest_Info"
BI = "Newera/Data/DataTables/GOP_Battle_Info"
TC = "Newera/Data/DataTables/Text/en/GOP_Text_Common"
PARAM = "Newera/Data/DataTables/GOP_Battle_UnitParam"
JOB = "Newera/Data/DataTables/GOP_Battle_Job"
# Enemy rows used by the cut battles whose class and growth rows were deleted with the cut content [read]:
# (param row, the class id it references, the party character whose class/growth it should mirror).
ENEMY_CLASSES = [
    ("BATTLE_UNITPARAM_CH_N402", "BATTLE_JOB_CH_N402_1", "P002"),   # Roland (duel)
    ("BATTLE_UNITPARAM_CH_N403", "BATTLE_JOB_CH_N403_1", "P003"),   # Benedict (duel)
    ("BATTLE_UNITPARAM_CH_N404", "BATTLE_JOB_CH_N404_1", "P004"),   # Frederica (duel)
    ("BATTLE_UNITPARAM_CH_N001", "BATTLE_JOB_CH_N001_1", "P021"),   # Maxwell (Tourney, Test 41c)
    ("BATTLE_UNITPARAM_CH_011", "BATTLE_JOB_CH_N411_1", "P011"),    # Julio (Tourney, Test 41c)
]


def hero_abilities(c):
    """The character's class abilities in learning order, from the vanilla class rows (data/tables dump)."""
    j = json.load(open(os.path.join(HERE, "..", "..", "data", "tables", "GOP_Battle_Job.json"), encoding="utf-8"))
    j = j.get("rows", j)
    out = []
    for i in (1, 2, 3):
        r = j.get(f"BATTLE_JOB_CH_{c}_{i}", {})
        out += [r[f"LearnableAbility{n}"] for n in range(1, 11) if r.get(f"LearnableAbility{n}", "None") != "None"]
    assert 0 < len(out) <= 10, (c, out)
    return out
TE = "Newera/Data/DataTables/Text/en/GOP_Text_EventOverview"
TTB = "Newera/Data/DataTables/Scenario/Text/en/Text_Test_TextForBattle"
TDR = "Newera/Data/DataTables/Scenario/Text/en/Main/ms02_x02/Text_ms02_x02_battle_02_drama"
OPEN_FLAG = "WI_END_MS01_X01_PART_BATTLE_01_EX"  # set once Chapter 1's first battle is done: every real save has it

# key: (quest copy_from, battle-info row (existing) or (new row, copy_from), level name, title, map name, map image,
#       forced units, victory text id or None (= our own), victory English, description, levels by lap, sortie)
BATTLES = [
    dict(key="TOURNEY", title="(Cut Content) The Tourney Final", quest_from="QUEST_INFO_SITUATION_02_X02_BATTLE",
         bi="BATTLE_INFO_SITUATION_02_X02_BATTLE_02", bi_from=None, level="ms02_x02_battle_02",
         map_name="TEXT_COMMON_PLACE_A0_EX_GARDEN", map_img="P_ms02_x02_battle_01", forced=["UNIT_MASTER_CH_P002"],
         victory="TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_1", levels=(3, 35, 50), sortie=6,
         desc="A final round of the tourney that was cut from Chapter 2: Serenoa and Roland face Maxwell and Julio "
              "for the title. Restored from unused game data."),
    dict(key="ROLAND", title="(Cut Content) Roland's Defiance", quest_from="QUEST_INFO_SITUATION_17_X38_BATTLE",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_ROLAND", bi_from="BATTLE_INFO_SITUATION_15_X30_BATTLE",
         bi_main="BATTLE_INFO_SITUATION_17_X35_BATTLE",
         level="ms17b_x35_battle_01", map_name="TEXT_COMMON_PLACE_A1_IN_HALL", map_img="P_ms15_x30_battle_01", forced=[],
         victory=None, victory_en="Defeat Roland.", levels=(28, 50, 50), sortie=1,
         desc="A cut duel from Chapter 17: when the vote favours Benedict's plan, Roland stands against Serenoa "
              "one on one. Restored from unused game data."),
    dict(key="FREDERICA", title="(Cut Content) Frederica's Defiance", quest_from="QUEST_INFO_SITUATION_17_X38_BATTLE",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_FREDERICA", bi_from="BATTLE_INFO_SITUATION_15_X30_BATTLE",
         bi_main="BATTLE_INFO_SITUATION_17_X36_BATTLE",
         level="ms17r_x36_battle_01", map_name="TEXT_COMMON_PLACE_A1_IN_HALL", map_img="P_ms15_x30_battle_01", forced=[],
         victory=None, victory_en="Defeat Frederica.", levels=(28, 50, 50), sortie=1,
         desc="A cut duel from Chapter 17: when the vote favours Roland's plan, Frederica stands against Serenoa "
              "one on one. Restored from unused game data."),
    dict(key="BENEDICT", title="(Cut Content) Benedict's Defiance", quest_from="QUEST_INFO_SITUATION_17_X38_BATTLE",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_BENEDICT", bi_from="BATTLE_INFO_SITUATION_15_X30_BATTLE",
         bi_main="BATTLE_INFO_SITUATION_17_X37_BATTLE",
         level="ms17f_x37_battle_01", map_name="TEXT_COMMON_PLACE_A1_IN_HALL", map_img="P_ms15_x30_battle_01", forced=[],
         victory=None, victory_en="Defeat Benedict.", levels=(28, 50, 50), sortie=1,
         desc="A cut duel from Chapter 17: when the vote favours Frederica's plan, Benedict stands against Serenoa "
              "one on one. Restored from unused game data."),
    dict(key="ROSELLE", title="(Cut Content) Routing the Roselle (Draft)", quest_from="QUEST_INFO_SITUATION_11_X20_BATTLE",
         bi="BATTLE_INFO_SITUATION_12_X23_BATTLE", bi_from=None, level="ms12_x23_battle_01",
         map_name="TEXT_COMMON_PLACE_A1_EX_VILLAGE", map_img="P_ms11_x20_battle_01",
         forced=["UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_P004"],
         victory="TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_1", levels=(19, 43, 50), sortie=None,
         desc="An early draft of the battle against Jerrom: rain, barricades and Rufus at your side, on an older "
              "version of the map. Restored from unused game data."),
    dict(key="RIVER", title="(Cut Content) The Norzelia River (Test)", quest_from="QUEST_INFO_SITUATION_14_X29_BATTLE",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_RIVER", bi_from="BATTLE_INFO_SITUATION_14_X29_BATTLE",
         level="ms14_x29_battle_02", map_name="TEXT_COMMON_PLACE_A0_EX_SHIP01", map_img="P_ms14_x29_battle_01",
         forced=["UNIT_MASTER_CH_P002"],
         victory="TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_14", levels=(22, 47, 50), sortie=None, fieldinfo=False,
         desc="A cut second battle on the Norzelia River: Serenoa's forces board Avlora's ship. "
              "Restored from unused game data."),
    # Round 2 (user 2026-11-22): three older versions of late-game battles. Their levels were never shipped; each runs on
    # a renamed copy of the shipped level its units fit (maps/clone_levels.py). "script" = the old Lua script.
    dict(key="IDORE_OLD", title="(Cut Content) Fighting Idore (Early)",
         quest_from="QUEST_INFO_SITUATION_19_X45_BATTLE_02",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_IDORE_OLD", bi_from="BATTLE_INFO_SITUATION_19_X45_BATTLE_02",
         level="ms19_x45_battle_02", script="ms19_x45_battle_02_old", mapcfg="BATTLE_MAPCFG_MS19_X45",
         map_name="TEXT_COMMON_PLACE_A3_WATERFALL", map_img="P_ms19f_x45_battle_02", forced=[],
         victory="TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_1", levels=(33, 50, 50), sortie=None, fieldinfo=False,
         defeat=("TEXT_COMMON_BATTLE_UI_DEFEAT_CONDITION_1", "None"),
         desc="An earlier version of the battle against Idore at the waterfall, with a different Hyzantine force and "
              "Roselle fighters on the enemy side. Restored from unused game data."),
    dict(key="LYLA_OLD", title="(Cut Content) Fighting Lyla (Early)",
         quest_from="QUEST_INFO_SITUATION_21_X48_BATTLE",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_LYLA_OLD", bi_from="BATTLE_INFO_SITUATION_21_X48_BATTLE",
         level="ms21_x48_battle_01", mapcfg="BATTLE_MAPCFG_MS21_X48",
         map_name="TEXT_COMMON_PLACE_C0_CITY", map_img="P_ms21s_x48_battle_01", forced=[],
         victory="TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_1", levels=(33, 50, 50), sortie=None,
         desc="An earlier version of the battle against Lyla in the streets of Hyzante, with a different enemy force. "
              "Restored from unused game data."),
    dict(key="FINAL_OLD", title="(Cut Content) The Final Battle (Early)",
         quest_from="QUEST_INFO_SITUATION_21_X48_BATTLE_02",
         bi="BATTLE_INFO_SITUATION_TSMOD_CUT_FINAL_OLD", bi_from="BATTLE_INFO_SITUATION_21_X48_BATTLE_02",
         level="ms21_x48_battle_02", mapcfg="BATTLE_MAPCFG_MS21_X48_2",
         map_name="TEXT_COMMON_PLACE_C0_IN_AUDIENCE", map_img="P_ms21s_x48_battle_02", forced=[],
         victory=None, victory_en="Defeat Idore.", levels=(35, 50, 50), sortie=None,
         desc="An earlier version of the final battle: Idore and the Hierophant together in the audience hall, "
              "surrounded by Automatons. Restored from unused game data."),
]
ROUND2 = ("ms19_x45_battle_02", "ms21_x48_battle_01", "ms21_x48_battle_02")

# Duels (Test 41b): the draft levels use the castle hall (A1_IN_Hall), the map of the shipped Chapter 15 battle
# "Patriatte's Gambit" (15_X30): its place name, picture and battle-setup row (indoor map config), not Chapter 7's streets.

# English for the cut duel and river lines (Japanese originals in Scenario/Text/jp/Text_Test_TextForBattle;
# the shipped English table holds garbled copies). \r\n = second balloon line, as in the Japanese.
LINES = {
    3501: "I see you've steeled yourself.",
    3502: "I never thought it would come to a contest between you and me.",
    3503: "I always knew a time like this would come someday.",
    3504: "You're a man who can't bend his convictions, after all.",
    3505: "I carry the fate of everyone.",
    3506: "I have to see it through.",
    3507: "As one of the royal family, I have burdens of my own to bear.",
    3508: "You've never changed in that respect.",
    3509: "You seem awfully composed.",
    3510: "Time I got serious.",
    3511: "You've grown.",
    3512: "But so have I.",
    3513: "Ngh... As expected of you...",
    3514: "But I'm not beaten yet!",
    3515: "This ends now!",
    3601: "I will give it everything I have.",
    3602: "Do you truly believe you can defeat me?",
    3603: "It is not a question of winning or losing.",
    3604: "I simply mean to give you all my strength.",
    3605: "I see... Your resolve is firm.",
    3606: "Then I'll fight in earnest as well.",
    3607: "Ngh... A remedy, then...",
    3608: "So you had something held in reserve.",
    3609: "I know full well how strong you are, Lord Serenoa.",
    3610: "Just a little more...",
    3611: "Is she building up her TP?",
    3612: "This will decide it!",
    3613: "Now face my greatest spell!",
    3614: "It's decided.",
    3701: "Let me see what you are truly capable of, young master.",
    3702: "Young master... It's been a long time since anyone called me that.",
    3703: "To me, young master, you will always be the young master.",
    3704: "With the others present,\r\nI thought I would never call you that again...",
    3705: "I'm surprised myself.",
    3706: "I never imagined I would have to face you, Benedict.",
    3707: "You have grown into a fine man.",
    3708: "Then why not walk the path I've chosen with me?",
    3709: "That I cannot do.",
    3710: "Think of me as a wall you must overcome.",
    3711: "A wall...",
    3712: "The difference in strength is plain.\r\nSo the wall must be one of the spirit.",
    3713: "Just so.",
    3714: "To move forward, there are things one must leave behind.",
    3715: "Understood!\r\nThen I will overcome you!",
    2930: "We've drawn alongside. Board them!",
    2970: "What a racket.",
    2971: "My apologies!\r\nThe enemy has broken through.",
    2972: "No matter. We'll drive them all back.",
}


def add(ed, table, row, copy_from, fields):
    """Copy a row, then set each field with a single-field edit (add_rows' 'set' can't write Str fields)."""
    ed.append({"table": table, "add_row": row, "copy_from": copy_from})
    for f, v in fields.items():
        ed.append({"table": table, "row": row, "field": f, "value": v})


def main():
    ed = []
    for b in BATTLES:
        k = b["key"]
        q = f"QUEST_INFO_TSMOD_CUT_{k}"
        title = f"TEXT_COMMON_BATTLE_UI_BATTLE_NAME_TSMOD_CUT_{k}"
        desc = f"TEXT_EVENTOVERVIEW_TSMOD_CUT_{k}"
        vic = b["victory"] or f"TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_TSMOD_CUT_{k}"
        forced = (b["forced"] + [""] * 5)[:5]
        # Test 41c [tested]: the duel levels have shipped setup rows (17_X35/36/37) and the game reads the first row whose
        # LevelName matches the level (prep screen title showed the shipped row's missing text id). Point the picker at
        # those rows and edit them; our earlier copies stay (a save may reference them) but are no longer used.
        sit = b.get("bi_main", b["bi"])
        qset = {"BattleSituationId": sit, "TitleTextId": title, "ContentTextId": desc,
                "MapNameTextId": b["map_name"], "MapImage": b["map_img"], "OpenFlag": OPEN_FLAG, "OpenFlag2": "",
                "CloseFlag": "", "CloseFlag2": "", "ClearFlag_Normal": "", "ClearFlag_Hard": ""}
        for i, u in enumerate(forced, 1):
            qset[f"ForcedSortieUnit{i}"] = u
        add(ed, QI, q, b["quest_from"], qset)
        lv = b["levels"]
        bset = {"TextId": title, "VictoryConditionTextId_1": vic, "Level": lv[0], "Level_2": lv[1], "Level_3": lv[2],
                "ClearFlag1": "", "ClearFlag2": "", "ClearFlag3": "", "ClearFlag4": "", "AfterBattleFlag": ""}
        if b.get("bi_main"):
            for f, v in dict(bset, MapCfgID="BATTLE_MAPCFG_MS15_X30", MaxSortieNum=1).items():
                ed.append({"table": BI, "row": b["bi_main"], "field": f, "value": v})
        if b.get("mapcfg"):
            bset["MapCfgID"] = b["mapcfg"]
        # User 2026-11-22: the copied shipped rows brought their walkthrough prompt (FieldInfo) and the shipped
        # battle's defeat text ("Allow even a single Rosellan to fall"); the Tourney row allowed 8 for 6 tiles.
        if b.get("fieldinfo") is not None:
            bset["FieldInfo"] = b["fieldinfo"]
        if b.get("defeat"):
            bset["DefeatConditionTextId_1"], bset["DefeatConditionTextId_2"] = b["defeat"]
        if b["sortie"] and not b["bi_from"] and not b.get("bi_main"):
            bset["MaxSortieNum"] = b["sortie"]
        if b["bi_from"]:
            bset["LevelName"] = b["level"]
            if b["sortie"]:
                bset["MaxSortieNum"] = b["sortie"]
            add(ed, BI, b["bi"], b["bi_from"], bset)
        else:
            for f, v in bset.items():
                ed.append({"table": BI, "row": b["bi"], "field": f, "value": v})
        add(ed, TC, title, "TEXT_COMMON_BATTLE_UI_BATTLE_NAME_2_2", {"Text": b["title"]})
        if not b["victory"]:
            add(ed, TC, vic, "TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_14", {"Text": b["victory_en"]})
        add(ed, TE, desc, "TEXT_EVENTOVERVIEW_MS02_X02_PART_BATTLE_01", {"Text": b["desc"]})
    for n, t in LINES.items():
        ed.append({"table": TTB, "row": f"Text_Test_TextForBattle_{n}", "field": "Text", "value": t})
    tr = json.load(open(os.path.join(HERE, "..", "..", "tools", "cut_sweep", "translations.json"), encoding="utf-8"))
    for rid, t in tr.items():
        if rid.startswith("MS02_X02_BATTLE_02_DRAMA_"):
            ed.append({"table": TDR, "row": rid, "field": "Text", "value": t})
    lua = {f"src/{b['level']}_append.lua": f"Newera_Handling/Scenario/Story/{b['level'].split('_battle')[0]}/{b.get('script', b['level'])}"
           for b in BATTLES}
    # The old Idore script requires a scene module that doesn't ship (ms19_x45/scene/ms19_x45_battle_S_02), and an append
    # runs after that require fails: replace the script with its own source minus that line (make_lua.py writes it).
    full = {"src/ms19_x45_battle_02_old.lua": "Newera_Handling/Scenario/Story/ms19_x45/ms19_x45_battle_02_old"}
    # Test 41b [tested]: the duel enemy rows (N402/N403/N404) reference a class (BATTLE_JOB_CH_N40x_1) and growth table
    # (BATTLE_UNITGROWTH_CH_N40x) that no longer exist, and SpawnUnit crashes on them. Recreate each class the way shipped
    # enemy versions of party characters are built (Travis: BATTLE_JOB_CH_N414_x vs P014_x [read]): a copy of the hero's
    # rank-3 class with no promotion links or medal, rank DEFAULT, the generic enemy help text, and every class ability
    # at level 0. Growth: the hero's own rank-3 table in all three slots (enemy rows use one table for all three).
    for row, job, c in ENEMY_CLASSES:
        abilities = hero_abilities(c)
        fields = {"eJobRank": "EJobRank::DEFAULT", "JobTypeBefore": "None", "JobTypeAfter1": "None",
                  "JobTypeAfter2": "None", "JobTypeAfter3": "None", "JobTypeParallel1": "None",
                  "JobTypeParallel2": "None", "iNecessaryUnitLevel": 0, "NecessaryItem": "None",
                  "JobHelp": "TEXT_JOB_HELP_SOLDIER", "CorrectParam": "None", "AutoSupportAbility1": "None",
                  "AutoSupportAbility2": "None", "SpriteId": ""}
        for i in range(1, 11):
            ab = abilities[i - 1] if i <= len(abilities) else "None"
            fields[f"LearnableAbility{i}"] = ab
            fields[f"iLearnableLevel{i}"] = 0
        add(ed, JOB, job, f"BATTLE_JOB_CH_{c}_3", fields)
        for f in ("UnitGrowthTable", "UnitGrowthTable2", "UnitGrowthTable3"):
            ed.append({"table": PARAM, "row": row, "field": f, "value": f"BATTLE_UNITGROWTH_CH_{c}_R3"})
    # Test 41b [tested]: three levels hang while loading; maps/fix_levels.py drops their WorldMapLevel sublevel.
    raw = {}
    for lv, fo in (("ms02_x02_battle_02", "ms02_x02"), ("ms14_x29_battle_02", "ms14_x29"), ("ms12_x23_battle_01", "ms12_x23")):
        for ext in ("umap", "uexp"):
            raw[f"maps/out/Newera/Map/Story/{fo}/{lv}.{ext}"] = f"Newera/Map/Story/{fo}/{lv}.{ext}"
    # Round 2: renamed copies of shipped levels (maps/clone_levels.py).
    for lv in ROUND2:
        fo = lv.split("_battle")[0]
        for ext in ("umap", "uexp"):
            raw[f"maps/out/Newera/Map/Story/{fo}/{lv}.{ext}"] = f"Newera/Map/Story/{fo}/{lv}.{ext}"
    mod = {"name": "TSMod_CutBattles",
           "note": "The nine cut story battles in the story-battle picker (mods/cutbattles_proposal.md). Generated by make_mod.py.",
           "lua": full, "lua_append": lua, "raw_files": raw, "dt_edits": ed}
    with open(os.path.join(HERE, "mod.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(mod, f, ensure_ascii=False, indent=1)
    print(len(ed), "edits;", len(lua), "lua appends")


if __name__ == "__main__":
    main()
