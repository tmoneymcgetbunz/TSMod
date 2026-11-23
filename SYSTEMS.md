# Triangle Strategy (PC): game systems, and what we can mod

Written 2026-11-16. Sources:
- the game files: 80 DataTables dumped to `data/tables/*.json`, 3,759 decompiled Lua scripts in `decompiled/`, and the battle level packages;
- our own in-game tests;
- public mods and the community's modding Discord channels.

Confidence tags: **[tested]** proven in-game by us · **[read]** read directly from game data or scripts · **[community]** reported by other modders, not verified by us · **[inferred]** reasoning, not yet checked.

---

## 1. How the game is put together

| Layer | What lives there | Can we change it? |
|---|---|---|
| **C++ engine** (`TRIANGLE_STRATEGY-Win64-Shipping.exe`, module `/Script/Newera`) | Damage math, pathing, AI move/target decisions, turn order, UI, save serialization, the "native" Lua commands (about 1,140 of them, see `lua_commands_raw.txt`) | No (only exe patching, which we haven't attempted) |
| **DataTables** (`Content/Newera/Data/DataTables`, 80 top-level + localized text) | Almost every number and link: units, classes, weapons, abilities, buffs, terrain, items, shops, quests, battles, text | **Yes.** Field edits, new rows and new names **[tested]** |
| **Lua 5.1 scripts** (`Content/LuaScriptBin/Src`, encrypted `.lub`) | Story flow, every battle's setup and events, AI ability rules, menus and encampment flow | **Yes.** Replace or append **[tested]** |
| **Unreal assets** (`.umap` levels, WhiteBox grid assets, sprites (Paper2D), effects, sounds) | Battle maps and their terrain grid, AI zone actors, camera, character sprites and animations | Partly. Byte-level edits only; new art needs the UE 4.27 editor (§9) |
| **Save data** (GVAS → self-keyed NWER blob) | Unit records (level, EXP, *learned abilities*, battle-param id), flags, inventory, gold | **Yes.** `tools/tssave.py`, `tools/tsunits.py` **[tested]** |

Mods load as `*_P.pak` patch paks (no signing). Two paks that ship the same file override each other, so combine mods with `build_mod.py`.

---

## 2. Battles end to end

### 2.1 The chain [read]
```
GOP_Quest_Info  (mock battle / story replay entry in the encampment list)
   └─ BattleSituationId → GOP_Battle_Info (level name, map config, victory/defeat text, recommended level,
                                          max sortie, turn limit, kill count, clear flags)
         ├─ MapCfgID → GOP_Battle_MapCfg (start time of day, weather table, wind table, win-condition type)
         └─ LevelName → Map/Story/<id>/<battle>.umap   (small wrapper level, class NeweraBattleLevel)
                ├─ LuaScriptName  = "Scenario/Story/<id>/<battle>"   ← the battle script
                ├─ levelWhiteBoxAsset → Map/WBAsset/<id>/<battle>   (baked terrain grid + camera limits)
                ├─ streams the environment: Map/Common/<region>/<map>_GFX / _OTH / _WB + StandBy + camera sublevels
                └─ (story battles) BP_AISettingActor actors tagged AI_LAND, AI_DF, AI_TRA, … (AI zones, §3)
```
- Launch: `QuestCommon.OnQuestStart` → `OpenLevel(LevelName)`. The level's own `LuaScriptName` decides which script runs. `GOP_Battle_Info.ScriptName` is only informational.
- **Mental mock battles** = `GOP_Quest_Info` rows of category `IMAGE_BATTLE` (35 of them). They use 30 `sq0x_battle_0y` levels in 10 environments.
- **Story replays** = `STORY_BATTLE` (57 rows).

Quest rows also control:
- **availability:** `ChapterNum`, `OpenFlag`/`CloseFlag`;
- **forced units:** `ForcedSortieUnit1..5`;
- **rewards:** `Reward`, `RewardInfo`.

### 2.2 A battle script [read]
Every battle script fills in the hooks of `ClassBattleBase` / `ClassBattle` (`Scenario/CommonDef/ClassBattleBase.lua`):
- `SETTING_VALUES`: map config id, intro camera, BGM, field-name text → `OverrideSetting`
- `SetupInitialPositionAndUnit_Implementation`:
  - `AddInitialPosition(x, y, dir)` for the deploy squares;
  - `AddEnforceMissionUnits` / `AddInitialMissionUnits` for forced units;
  - `SetInitialChargeTime` for initial turn timers.
- `SpawnEnemyAndNeutralUnit_Implementation`, for each enemy or neutral unit:
  - `SpawnUnit(tag, UNIT_MASTER_…, BATTLE_UNITPARAM_…, x, y, dir, ox, oy)`;
  - `LevelUpToTargetLevel(tag, lv)` and `LevelUpWeaponOnMapUnit(tag, wlv)`;
  - `ChangeDropItemGopId(tag, ITEM_DROP_…)` for drops.
- `SpawnAndChangeMapGimmick` / `SpawnAndChangeMapStaticActor`: traps, objects, `StartAction(actor, anim)`
- `SetupEventTriggers_Implementation`: `AddEventTrigger(func, prio, BATTLE_TURN|…, …)`, i.e. turn-, position- and kill-based events
- Victory and defeat: `BattleEndCheckTable.VictoryFunc / LoseFunc`, re-checked after every action **[tested]** (the test kit's "win on first kill")
- `PreStartBattle`, `PostResultVictory`, `PostResultLose`, `DefeatAndGo`: before and after logic
- Mid-battle tools: `ChangeAISettings(unit, tag)`, reinforcements through generate points (`CreateGeneratePointOnMapEx` + `GenerateUnitFromGeneratePoint`), `ChangeBGM`, `AddHP`, dialogue and sequence calls.

A full mock battle script is about 250 lines, mostly data (`sq01_battle_01.lua`).

### 2.3 Custom battles: three tiers
| Tier | What | New UE assets? | Feasibility |
|---|---|---|---|
| **A. Re-script an existing battle** | Replace or append the `.lub` of an existing mock battle: new enemy lineup, positions, levels, drops, triggers, win conditions | No | **Easy.** Same technique as the Ch.1 test kit **[tested]** |
| **B. New entry in the mock battle list** | `add_row` a `GOP_Quest_Info` + `GOP_Battle_Info` (+ text rows). Point `LevelName` at an existing `sq` level. In that level's script, branch on the native `GetCurrentQuestInfoId()` to run our setup instead | No | **Very likely.** All pieces exist (row-adding is proven). Needs a `StrProperty` edit in `build_mod` for text. Untested in-game |
| **C. New wrapper level** (same environment, own script and AI zones) | Clone `Map/Story/sqXX/*.umap` under a new package name with a different `LuaScriptName`, and optionally a new WhiteBox asset | Cloned/renamed | **Medium.** Needs package renaming (an extension of `uasset_edit`) |
| **D. Brand-new map geometry** | New environment art + grid | Yes (UE editor) | **Hard**, see §9 |

**Tier B is proven in-game (2026-11-16, `mods/mock_custom01`, "Gustadolph's Gambit").** Checklist for future custom battles:
- **Rows:** add `GOP_Quest_Info` + `GOP_Battle_Info` + text rows. Set `ClearFlag_Normal/Hard` to `""` unless you want to share vanilla clear flags.
- **Script:** branch with `GetCurrentQuestInfoId()` and wrap `SetupInitialPositionAndUnit` / `SpawnEnemyAndNeutralUnit`. Mock battle levels have no AI zones, so units roam freely.
- **AI:** mock battles leave `g_ActiveAIUnitFunction` nil, so set `g_ActiveAIUnitFunction = CallUnitAIFunc` or enemies won't use scripted skills **[tested]**.
- **Victory:** a custom condition goes in `BattleEndCheckTable.VictoryFunc` **[tested]**.
  - The **in-battle menu's victory line** comes from `SETTING_VALUES.VictoryRequirementText`, not `GOP_Battle_Info` (that only feeds the Tavern list and briefing). Set it via `OverrideSetting` in the custom branch. **[untested fix]:** it's built into `mock_custom01` but not checked in-game.
  - Optional, untested: a new `GOP_Battle_MapCfg` row with `eWinConditionType::KNOCKDOWN` for boss-style handling.

**Mock battle availability:** quest rows are gated by chapter and flags. A custom quest can be opened with `OpenFlag=""` and `ChapterNum` low, so it shows up immediately **[inferred]** from vanilla rows.

---

## 3. AI: four layers

1. **Native decision engine (C++).** Picks where to move and whom to hit (`SYS_WaitAIDecide` → `GetAIAction`). It uses unit stats and `GOP_Battle_UnitParam.eUnitAIType` (NORMAL = AI, NONE = player-controlled **[tested]**), `fEvaluationHP`, and `CorrectParam.bIgnoreAIEvaluation`.
   - It doesn't consider counters, resistances or many passives **[community: Mayday]**.
   - It ignores pure-utility skills unless layer 3 tells it to use them **[community]**.
   - **Not moddable** except through its inputs.
2. **Map layer: AI zones.** These are `BP_AISettingActor` actors inside the battle `.umap`, each with a tag (`AI_LAND`, `AI_DF`, `AI_FREE`, `AI_TRA`…) and components:
   - `AIRestrictMoveSetting` / `AIRestrictAttackSetting`: tile lists where units may move or attack from;
   - `AINormalSetting`, `AIAbilitySetting`, `AISupportSetting`, `AIClimbWallSetting`.

   Battle Lua assigns units to zones and switches them on triggers: `ChangeAISettings("DAG1", "AI_DF")` (1,383 calls across story scripts). Generic presets `AISetting1-5`, `Boss1-3`, `AIBow`, `Escort`, `Assassin` are referenced by maps **[community: Mayday/thuban9]**. This explains "idle boss until you cross a line" and "bowmen hold the roof".
   - *Modding:* re-assigning existing zones is Lua-only (easy). **New zones mean editing the umap's tile arrays** (thuban9: UAssetGUI can't resize arrays). Our byte tools could, but that isn't built.
   - Mock-battle levels have **no** AI-setting actors. Their units use default behaviour (layer 1 + 3).
3. **Unit layer: ability rules.** `UnitParam.AITag` → `CallUnitAIFunc` → `AI_<tag>()` in `Battle/BattleAIFunc{M00..M50,N00,P00}.lua`. That gives per-turn rules:
   - `AIUtil_UseAbilityBasic/Random/HPRate/TargetHPRate/AroundNoEnemy/NotBuffed/NotBadConditions/UnitNumber` (cooldown, TP window, target conditions);
   - `AISetNormalAbilityProbability`;
   - `AISetMovePatternAfterActcion(Safety|Shortest)`.

   Job-type defaults: mages and healers retreat if enemies are within 5 tiles, mages don't melee unless adjacent, and healers heal at 90/75%.
   - **Fully moddable in Lua.** Mayday's overhaul is built here. Caveat: `AIUtil_*` helpers are inconsistent, and some rules are overridden per map **[community]**.
4. **Battle-script layer.** The bottom of each battle Lua adds map-specific unit logic: retreat scripts, escort switches, Idore's puppet spawning, Lyla's skill rotation **[community + read]**.

**Custom-battle AI recipe:** give enemies an `AITag` whose `AI_<tag>` function exists, or append new `AI_*` functions plus `elseif` branches. On maps without zones they act freely. For "hold position" behaviour without zones, use Lua triggers (wait, then `ChangeAISettings`) **[inferred]**.

---

## 4. Units and characters

### 4.1 Data chain [read/tested]
```
GOP_Unit_Master[UNIT_MASTER_CH_X]   who: name/full-name text, eCharacterId, SpriteType, footsteps, voice set,
                                     FaceId, UnitAttachedDataSetId (profile entries), bGrowthUnit, GrowthUnitBattleParamId,
                                     bNewGameMember, belief/vote links
   └─ GOP_Battle_UnitParam[...]      how it fights: camp, AI type, AITag, guest, EXP on/off, growth tables (1-3),
                                     UnitClass (→ Job), EquippedWeapon, resistances, height, flags
         ├─ GOP_Battle_UnitGrowth[<table>_<lv>]   per-level stats, levels 1-60 (11,160 rows)
         ├─ GOP_Battle_Job[...]       class: type, rank, JobTypeAfter* (promotion), needed level/item,
         │                            SpriteId, CorrectParam, auto-support abilities, LearnableAbility1..10 @ level
         └─ GOP_Battle_Weapon[...]    weapon: type, SpriteId, AttackParam, rank-up chain, MaxLv, upgrade costs,
                                      WeaponAbilityTree (→ 5 nodes per rank) + WeaponAbilityMaterial
```
- **Prefixes:**
  - `P001–P030`: recruits;
  - `P031–P047`: guests;
  - `P100`: Piccoletta's Decoy (**exe hard-codes it**);
  - `N…`: named NPCs and bosses (`_E` = enemy variant);
  - `G…` jobs: green ally variants;
  - `M0xx_…`: generic soldiers (A Glenbrook / B Aesfrost / C Hyzante; SWD SLD SPR BOW BOK ROD DAG RID CLB).
- **Recruiting an NPC:**
  - New Game route works **[tested]**;
  - existing save works with record injection **[tested]**;
  - own param row **[tested]**.


### 4.2 Pressure points
- **Learned abilities live in the save**, written on level-up and promotion from the Job table. Editing a class's abilities doesn't change existing units until promotion or a New Game **[community; consistent with our Sycras "Cheer only"]**. Workarounds:
  - set the learn table before the unit joins;
  - add abilities via the weapon tree (Dogistan);
  - write the save record with `tsunits` **[inferred]**.
- **Stats are rebuilt from tables at battle start** (save stat edits are overwritten) **[community: Shane Qi, exe]**.
- **Unit records are only created at New Game** for growth units, and `JoinParty` can't create one **[tested]**. Recruiting into an existing save needs `tsunits inject`.
- **ECharacterId** is a fixed 114-value C++ enum. A brand-new character must reuse an existing id (NPC ids are plentiful). Most systems key on the unit-master row, not the enum **[read]**.
- **Sprites and animations:** 116 folders in `Content/Newera/Character/<id>/`, Paper2D flipbooks with per-character animation sets.
  - Skills point at animations via `GOP_Battle_AttackParam`.
  - A unit missing an animation shows a grey "dummy" sprite, or briefly turns into the skill's owner **[community]**.
  - Fix: repoint AttackParam to generic animations (Mayday).
  - **Battle movement uses L-shaped paths, so diagonal-walk gaps only matter in exploration** (observed in game).
  - Sycras has his own `ATK_Arrest` and `ATK_Cheering` animations.
- **Weapon sprite is baked into the character sprite.** You can't give a unit a different weapon type visually **[community: Mayday]**.
- **NPC weapons have no ability tree.** Opening Jens's menu for them crashes **[tested]**. Fix: add a `WeaponAbilityTree` and `RankUpWeapon` chain (done by `gen_recruit.py`, works **[tested]**).
- **Weapon skills [tested]:**
  - **Wiring:** the rank-3 weapon's `Ability` = the skill, which must also be a node in the rank-3 tree.
  - **The ability row must have** `bIsWeaponAbility=True` (registers the purchase as the weapon skill; corner-framed node), `bEnableCopy=False` (Copycat can't copy it) and `eFunctionIconTypeAbilityTree=UNIT_WEAPON` (weapon icon). All 30 vanilla weapon skills have exactly these.
  - **Battle-menu order** = `iSortNumber` ascending. Recruit commands are 10–70 and weapon skills 999 (last); NPC abilities are 1000+. A recruit built from NPC skills needs its weapon skill numbered above them, which the generator does (`max(learned)+1`). Sycras's Knock Back showed first with 999 [tested]; fixed build pending check.
  - **Even a passive weapon skill needs an `AttackParam`**. The registered skill becomes a battle command, and the hit/damage evaluation reads its attack data at battle load.
  - **On purchase**, the game writes the skill into a weapon-skill list in the unit's save record, right after the bought-node id list: count + `{FString id, i32 1, i32 0, FString id, i32 0}`. A purchase made while the flags were wrong stays unregistered until patched (`tsunits addwskill`).
- **Class changes on an existing save [tested]:** after repointing a unit's class id in its record, the ability list refreshes from the new class's learn table on load. Stored stats stay stale until promotion, level-up or battle start (or until written with the save tools). Promotion with medals works for generated classes.
- **Borrowed abilities [tested]:** Rufus's Armor Break on Sycras uses the generic attack animation and looks fine. Own abilities (Apprehend, Knock Back) use their own animations.
- **Promotion:** `Job.JobTypeAfter1..3` (+ `iNecessaryUnitLevel`, `NecessaryItem` medal). NPC jobs have none ("end of the path") **[tested]**.
- **Up to 10 abilities per job; the UI shows 7** **[community]**.
- **Faces / voices / profile:**
  - `Gop_Character_Face`, `GOP_Sound_ActionVoice` (35 voice sets), `GOP_Unit_Attached_Data(_Set)`, `GOP_Text_Character_Profile`;
  - new voice lines need audio assets **[inferred]**;
  - voice *sets* can be reused.

---

## 5. Abilities and combat data [read]
`GOP_Battle_Ability` (681) → `AttackParam` (650 rows, 99 fields: target, base type, element, height and direction correction, knockback, spread, friendly fire, status/buff ids, animation) → `CorrectParam` (421; flat and percent stat modifiers, reused by passives, accessories, classes and buffs) → `BuffEffect` / `BuffEffectAtk` (187/112) and `StatusEffect` / `StatusEffectAtk` (111/67).
- `Ability.eAbilityClassType` + `iParam/fParam/FNameParam` select special native behaviours, e.g. `FORCE_FLAME` with `BATTLE_FORCE_FLAME_BURNABLE` to set even non-flammable tiles ablaze **[community: thuban9]**.
- A skill's AI usage and its "role" tag must match or the AI won't use it (healers never heal with a mis-tagged skill) **[community]**.
- Plenty of unused or test abilities to repurpose: Serenoa's "Duel", stun, TP regen, aim, "prayer that clears the battle" **[community]**.
- Elements: fire/ice/wind/lightning interact with terrain flags (wet, freezable, conductive, burnable). Weather and wind tables modulate them (`GOP_Battle_Weather`/`Wind`, set per map in MapCfg).

---

## 6. Terrain and maps [read]
- **`GOP_Battle_Panel`** (44 terrain types): standable, enterable (also by flyers), move cost (100 = 1), hit/dodge modifiers, wet / freezable / puddle / snow / conductive flags, damage per turn (magma 40%, burning 20%, thorn 10%). Dynamic states include BURNING, BURNED, FREEZING, PUDDLE and SNOW.
- **Baked grid:** `Map/WBAsset/<id>/<battle>.bulkData` is a custom binary.
  - Header: version 2, size 21×21, then 441 cells, each a stack of layers. Bridges and roofs mean more than one layer per cell, e.g. 518 layers on sq01.
  - Each layer carries **a copy of its panel properties**: the panel-name text id, flags, move cost 100, etc.
  - ⇒ **Editing `GOP_Battle_Panel` probably doesn't change existing maps.** That matches Mayday's "terrain changes don't work" **[inferred + community]**. Changing a map's terrain means rewriting `bulkData` (format partly decoded; a decoder/encoder is a contained project).
  - The editor source of the grid is the `_WB` sublevel's `BP_BaseBlock` actors (`tools/wbmap.py` renders them). The game reads the baked asset.
- Tile coordinates: about 100 units per tile in X/Y and about 38 per height step **[community: thuban9]**. Per-map tile/height CSVs for the main story exist (thuban9's `main_story_maps.zip`).
- Time of day, weather and wind come from `GOP_Battle_MapCfg`. Changing them mid-battle is Lua-easy (Mayday's rain/night/storm demo) **[community]**.
- Traps, barricades, bombs and turrets are "gimmicks" spawned in Lua (`CreateGimmickData`, `SpawnBattleGimmick`) **[read]**.

---

## 7. Items and economy [read]
| Table | Content |
|---|---|
| `GOP_Item_Battle` (43) | Consumables. Each is an AttackParam/Ability, price, `bUnownable` |
| `GOP_Battle_Accessary` (49) | Accessories = CorrectParam + optional Ability |
| `GOP_Item_UpgradeMaterial` (31), `GOP_Battle_WeaponAbilityMaterial` (51) | Upgrade materials and per-node costs |
| `GOP_Item_ClassMedal` (2) | Promotion medals |
| `GOP_Item_Drop` (739) | Enemy drop sets A/B/C + steal item and rate (per-enemy, per-battle variants) |
| `GOP_Item_Pickup` (6), `GOP_Quest_Info.Reward` | Battlefield pickups, mock battle rewards |
| `GOP_Shop_List` (296), `GOP_Exchange_List` (102) | Shops and the quartermaster, gated by flags, NG count and conviction, with stock refills |
| `GOP_Battle_Order` (10) | Quietus (Benedict's orders) |
| `GOP_Item_Negotiate` (26) | Persuasion items |

Adding new items = new rows + text, all within reach of the current tools. Icons are enums (`eFunctionIconType`), so new icons need art.

---

## 8. Story, flags, convictions, text
- Story = `SysGlobal.SCENARIO_ANCHOR` stepping through `Progress/ScenarioProgressData` anchors. World-map icons are `GOP_World_Icon` rows (410), each opening a scenario block `sb_*.lua` **[read/tested]**.
- Convictions: `GOP_Belief_Uplist`, `GOP_Select_Param`. Votes: `GOP_Unit_VoteParam`, `GOP_Vote_*`. Character stories: `GOP_Character_Story`.
- **Text:** `DataTables/Text/<lang>/GOP_Text_*` (19 tables × 9 languages, rows `SelfId` + `Text`). Scenario dialogue is in `DataTables/Scenario/Text/<lang>/…` (a table per scene).
  - New text = `add_row` + a string edit. `build_mod` needs a `StrProperty` (size-changing) edit; small extension.
  - A mod that only adds English rows shows nothing (or the key) in other languages **[inferred]**.
- Hidden **debug menu**: in `DefaultEngine.ini`, set `GameDefaultMap=/Game/Newera/Map/System/DebugTitle.DebugTitle`. You get BattleTest, a BGM player and slot load; many options crash **[community]**. There are also `TestGameFlow` and `Debug_*` scripts in the Lua.

### Explosives, traps and turrets (map objects) [read 2026-11-17]
- **Explosives** (`UNIT_MASTER_OBJ_SUPER_BOMB`, "Detonates in N turn(s)") appear only in Chapter 16's mine battle `ms16_x34`.
  - The battle's Lua plants them: `SpawnUnit` with the treasure-chest stats row, made untargetable, near enemies in a "bombarea" zone every few enemy turn-ends.
  - The engine runs the countdown (trigger type `SUPER_BOMB_TURN`) and the "Defuse the Explosive" command.
  - At zero, the engine interrupts. Lua plays `ExplodeSuperBomb` (visual only), and the battle's lose check returns a loss. The game-over is script, not engine.
- **Traps** (`EAbilityClassType::SET_TRAP`, Steel Trap): data-driven.
  - `FNameParam1` = object unit placed (ghost);
  - `FNameParam2` = visual, an `ActorAssetTable` row (`BATTLE_TRAP_DAMAGE` → `BP_ENV_co_TrapDamage`);
  - `FNameParam3` = ability fired on step.
- **Turret** (`SET_TURRET`, Automatic Turret, **Jens's (P020) rank-3 weapon skill**): the chain is data: `TURRET` `FNameParam1` → `TURRET_EXEC_CHECK` (class `AUTO_ATTACK_BY_BOW`, `FNameParam1` → `TURRET_EXEC`, physical 1.0, range 1–4) [read 2026-11-19]. It places `UNIT_MASTER_OBJ_TURRET` (hard-coded in the exe), which auto-attacks each turn via `TURRET_EXEC_CHECK` → `TURRET_EXEC`. `iParam1 5`, `iParam2 1` [inferred: lifetime, max count].
- **Unit visuals:** the `Data/DataAsset/UnitActor` data asset maps unit ids to actor blueprints (Explosives → `BP_ENV_co_Bomb000`, also `BP_ENV_co_MagicBomb`, `BP_Turret`).
- **Lua damage:** `BATTLE::AddHP` and `UI::ApplyDamage` exist.
  - The user-level override goes in `Documents\My Games\TRIANGLE_STRATEGY\Steam\Config\WindowsNoEditor\Engine.ini`, so no pak is needed.
  - Lua can only read the debug flags (`IsDebugSwitch`), not set them.
  - The in-battle opener (`DebugSubLevel`, input `DebugMenuOn` = Gamepad_Special_Left) depends on `NeweraDebugSetting.DebugMenuAssetClass`, which was stripped from Shipping [inferred: likely dead].

---

## 9. Custom maps: realistic assessment
**What a map is:**
- a wrapper `.umap`;
- environment sublevels: GFX (art), OTH (other), WB (whitebox blocks);
- a baked `LevelWhiteBoxAsset` (grid + camera);
- optional AI-zone actors;
- a Lua script and DataTable rows.

| Approach | Needs | Verdict |
|---|---|---|
| New battle on an **existing environment**, same grid | Tiers A–C of §2.3 | Feasible now |
| Existing environment, **different playable area / terrain** | Rewrite `bulkData` (decoder/encoder) to block or open tiles, change terrain types or heights | Feasible with a contained reverse-engineering task. Visuals won't change, so only small or logical changes look right |
| **New environment** (new geometry and art) | UE 4.27 editor + `github.com/Chirijiraden/TriangleStratProj` (Narknon's dummy-class project, 1,410 Newera headers incl. `NeweraBattleLevel`, `LevelWhiteBoxAsset`, `AISettingActor`; last updated 2022-12). Build the level with game or own art, cook, then **bake `bulkData` ourselves** (the project's C++ bodies are stubs, so the dev bake tool isn't there) | Hard but possible. The bake format is the critical path, and we can derive it by comparing `_WB` blocks to `bulkData` on existing maps |

Nobody in the community has made a new map. thuban9 (2022) moved units and added objects in existing battles via Lua.

---

## 10. Save system (for mods) [tested]
- Decrypt/encrypt: `tools/tssave.py`. Unit records: `tools/tsunits.py` (`list`, `inject`, `setstr`). Gold = int32 after the leader-name FString in s1.
- Mod-made units live in the save. A save with a modded unit needs that mod installed to load safely.
- `ContinueSaveData` / `AutoSaveData` are rewritten by any test run.
- Debugging without logs: have Lua call `AddGameMoney(code)` and read the gold from the save.

---

## 11. Our tooling: what's possible today
| Capability | Tool | Status |
|---|---|---|
| Pak read / write | `tspak.py`, repak | ✔ |
| Lua decrypt → decompile → recompile → re-encrypt, replace or append | `lubcrypt.py`, unluac, luac5.1, `build_mod.py` | ✔ tested |
| DataTable field edits (Name/Enum/Bool/Int/Float), row copy | `build_mod.py` | ✔ tested |
| **New DataTable rows + name-map growth** | `uasset_edit.py` via `build_mod` `add_row` | ✔ tested |
| String (text) edits that change size | `uasset_edit.set_str` via `build_mod` | ✔ tested |
| Bulk row inserts (e.g. 180 stat rows) | `uasset_edit.add_rows` via `build_mod` `add_rows` | ✔ verified vs vanilla, tested in game |
| Full recruit kit from a spec | `gen_recruit.py` | ✔ used for all 20 recruits, tested in game |
| Verify a build against vanilla | `verify_stage.py` | ✔ |
| Save decrypt/encrypt, unit records | `tssave.py`, `tsunits.py` | ✔ tested |
| Table dumps | `dump_tables.py` → `data/tables/` | ✔ |
| WhiteBox grid view | `wbmap.py` (editor blocks) | ✔ (read-only) |
| Baked grid (`bulkData`) decode/encode | — | todo (medium) |
| Level package clone/rename (new wrapper levels) | — | todo (medium) |
| AI-zone edits in umaps | — | todo (medium) |
| New art / sprites / animations | UE editor | out of scope for now |

---

## 12. Feasibility summary
| Goal | Feasibility | Main blockers |
|---|---|---|
| **NPC → playable recruit** | ✔ Done (New Game + existing save) | Full kit: weapon tree, promotions, learn table (data work) |
| **"New" character from existing art** (new name/stats/kit on an NPC's sprite) | High | Reuse an ECharacterId; text rows; animations limited to that sprite's set |
| **New character with new art** | Low–medium | Paper2D sprite sheets + animation sets in the UE editor |
| **Custom mock battle, existing map** | High | Text string edits (small). Test tier B in-game |
| **Custom AI behaviour** | High (Lua rules) / Medium (new zones) | Native decision engine is a black box; zone arrays are umap edits |
| **Terrain tweaks on existing maps** | Medium | Baked grid format |
| **New maps** | Low–medium, effortful | UE editor workflow + grid bake |
| **New items / accessories / abilities** (reusing effects and icons) | High | New icons and animations need art |
| **Rebalance anything numeric** | High | Learned abilities are save-stored; tables load at boot |

## 13. Suggested next experiments (cheap and informative first)
1. **Tier-B custom mock battle:** add `StrProperty` edits to `build_mod`, then a new quest + battle-info row on `sq01_battle_01`, branching on `GetCurrentQuestInfoId()`. Proves "custom battles from the encampment" with no new assets.
2. **Sycras full kit:** weapon tree + rank-up weapons + a promotion job + learn table. Test promotion on the slot-2 save.
3. **`bulkData` decoder:** compare `sq01_battle_01` grid against its `_WB` blocks. Then try one tile change, e.g. make a wall tile standable, to confirm the game reads the baked grid.
4. **Level clone (tier C):** rename a wrapper `sq` umap to a new package with its own script, to unlock unlimited custom battles per environment.

## Mounted sprites (cavalry) [read + tested 2026-11-16]
- Battle sprites live in `Content/Newera/Data/FlipbookOutput/<id>/Flipbook/<id>_<Anim>_<Override>_<Height>_CHARACTER`. Override is `DEFAULT`, `HORSE`, `MASK`, ...
  `Character/<id>/Frames` holds only the on-foot frames. The horse body is shared (`Character/Horse`).
- Units with a HORSE flipbook set: P002 Roland, P017 Hossabara, N204 Exharme, N301 Clarus. They're exactly the params with `eSpecificEffectType2 = CAVALRY`, plus the generic rider soldiers (Unit_Master `SpriteType HORSE`).
  The tag selects the mounted set in battle [inferred, consistent with Exharme: enemy forms mounted, guest form untagged].
- Scenes switch it with Lua `OverrideAnimationType(actor, ENeweraFlipbookOverrideTypeHORSE)`. Per-class switching isn't in the tables (Job `SpriteId` is unused).

### Sprite lookup table: `Data/DataAsset/FlipbookStatic` [read + tested]
- `AnimationDatasEx: Map<ECharacterId, {Objects: Map<{AnimationType, NeweraFlipbookOverrideType, WeaponRank(DEFAULT/MIDDLE/HIGH)}, SoftObjectPath AnimationData>}>`, covering 102 characters.
- The `_DEFAULT/_MIDDLE/_HIGH` suffix on flipbook names is this WeaponRank key, not a height.
- **Class rank picks the override suffix**:
  - `EJobRank` MIDDLE → `*_RANK2`, HIGH → `*_RANK3` (e.g. HORSE_RANK3 for an Elite cavalry unit, RANK3 for Serenoa's Elite outfit);
  - missing keys fall back to the plain DEFAULT set (on foot).
- Menus use `EAnimationType::UIC_BattleIdle`. Several NPCs (N204, N301, P017) have only the placeholder `Character/000` frames for their on-foot menu sprite.
- Editing: `tools/flipbook_static.py` (`show <CHAR>`; mod.json key `flipbook_static`: `copy_override` / `remap`). It uses existing names only; the main export is the last in the package. The asset is ~40 MB, so paks that include it grow to ~50 MB.
- Mounted frames: `Character/<id>/TypeHorse/Frames` (N204 has them too).

### Menu sprites [tested]
- Menus (roster, unit details, weapon-tree class icons) load the frames **by path**: `Character/<id>/Frames/UIC_battleidle0a01..04_LB` (PaperSprites).
  - They ignore the `UIC_BattleIdle` flipbook files and the `FlipbookStatic` table.
  - For a recruited NPC they read the plain `Frames/` folder at every class rank.
- N204/N301/P017 ship no `Frames/UIC_*`, which is why they show the grey placeholder (`Character/000`).
- Fix: copy a variant's UIC frames into `Frames/` (`sprite_clones` with `frames_from`). Copies keep their source textures.
- Battle sprites come from the flipbook assets: replacing one is loaded. The rank frame folders `TypeHorse_RankN`/`RankN` do nothing for battle (12e).

### Character blueprint sprite variants [tested]
- `Character/<id>/BP_<id>`, component `SpriteManagerComponent`:
  - `SpriteReplaceDestString` (= the id);
  - `DefaultAnimationDatas` (scene animations);
  - **`FlipbookOverrideDatas`**: `Map<ENeweraFlipbookOverrideType, {AdditionalUnitHeight, SubTypeIdString (frame folder under Character/<id>/), AnimationDatas}>`.
- The actor only uses variants listed there. Examples:
  - P002 Roland: HORSE_RANK2/3, HORSEMASK*, COLOR_A/B/C;
  - P017 Hossabara: HORSE, HORSE_RANK2 (reuses TypeHorse), HORSE_RANK3;
  - N204 Exharme / N301 Clarus: HORSE only;
  - N106: none.
- Edit with `tools/bp_sprite.py` (`show <CHAR>`; mod.json `bp_sprite` copy_override).
- Adding HORSE_RANK2/3 (folder TypeHorse) to BP_N204 made promoted Exharme mounted in battle. List sprites in the roster and smithy still use the plain `Frames/` set for N204 (P002/P017 get their horse set there, cause unknown).
- **Which set a unit uses [read, 2026-11-20]:**
  - `GOP_Unit_Master.SpriteType` picks the override for a unit master: `N201` (the Hierophant) = `COLOR_A`, `N201_2` (puppet/boss) = `DEFAULT`, `N206` (Idore, Priest) = `DEFAULT`, `N206_2` (Demigod) = `BIGBOSS`.
  - Cavalry also comes from the param tag `eSpecificEffectType2 = CAVALRY` (the HORSE set).
  - `COLOR_A` and `BIGBOSS` ship rank flipbooks for all three ranks (`_DEFAULT/_MIDDLE/_HIGH_CHARACTER`); HORSE ships only the base rank.
- **`Type*` folders can be partial:**
  - N201 `TypeA/Frames` has only the recoloured poses, without the staff (`magicstick0a`) or attack (`atkswd0a`) poses, yet the vanilla Hierophant casts in COLOR_A. So missing poses fall back to `Frames/` [inferred].
  - Idore's BIGBOSS (`TypeA`) set lacks the staff pose, so his Priest spells would fall back to the small Priest frames.
  - `anim_check.py --variant TypeA` checks one set strictly; read its BAD results with that in mind.
- **Clarus (Batch C) [tested]:** the same recipe as Exharme, all working:
  - the CAVALRY tag;
  - `bp_sprite` HORSE_RANK2/3 → TypeHorse;
  - 696 animation clones + FlipbookStatic entries;
  - the menu `UIC_` frames cloned from `TypeHorse` into `Frames/`.

  He shows on foot in the roster/smithy lists, as Exharme does (his on-foot set exists, so no grey). Every pose was checked against the horse frames with `anim_check.py N301 --variant TypeHorse`.

### Difficulty [read 2026-11-16, deeper pass]
- Four levels; native enum `EGameDifficulty`: VERRY_EASY (sic), EASY, NORMAL, HARD (UI text calls Hard `CHALLENGE`). Set at New Game (`SetNewGameDifficulty`, from title select − 2); changeable in Options outside battle. Lua sysvar `SYS_GAME_DIFFICULTY` (55).
- **Not in data or scripts:**
  - no DataTable/DataAsset holds difficulty multipliers (all 72 tables + BattleStatic/CommonStatic/NewGameData/OptionSettingStatic checked);
  - no Lua script reads the setting;
  - the only Blueprint touching it is the debug menu (all 20,864 non-art assets scanned for `GetGameDifficulty`/`EGameDifficulty`);
  - so all effects are compiled C++.
- **Story enemy levels do not depend on difficulty.** `*_battle_01_common.lua` picks levels by playthrough count `GAME_RESULT_COUNT` (e.g. Tourney Exharme Lv3 / 35 / 48 on runs 1 / 2 / 3+). Mock battles scale to party level (`GOP_Quest_Info.PartyLvMin/Max`) and have their own Normal/Hard (`ClearFlag_Hard`).
- Conviction rows `BELIEF_UPLIST_EasyBattle` (Liberty +1), `NormalBattle`, `HardBattle` (Utility +1) are awarded natively. Whether by game difficulty or mock Normal/Hard is unverified.
- Executable: Blueprint `GetGameDifficultyBP` exec thunk `0x1411c2660` → system object at `[0x144e0f1d0]+0x428` → getter `0x140d2f860` (`movzx eax, byte [rcx+0x37]`). Call sites of the difficulty byte were not traced (time-heavy).
- Community (unverified): higher difficulty = smarter AI (Samurai Gamers); "blanket damage multipliers, not stats" (Reddit claim); "same spoils regardless of difficulty" (Game8 heading).
- Mods editing unit tables apply on every difficulty.
- **Measuring it:** same mock battle, same enemy, same attack, on Very Easy vs Hard. Compare the enemy's details screen (level/HP/stats) and the attack forecast (damage, hit %).
- **Custom trap marker [tested]:** `SET_TRAP`'s `FNameParam1` names the ghost unit, whose model comes from `UnitActor`.
  - Give a trap its own ghost unit (a `GOP_Unit_Master` copy) plus a `unit_actor` entry (`tools/unit_actor.py`).
  - Only use blueprints with the `NeweraMapGimmickObject` parent; `NeweraSuperBombGimmick` brings the countdown, defuse and explode interrupt.
  - ~~Dragan's Blasting Charge uses the Aelfric Blast Crystal (`BP_ENV_co_MagicBomb`).~~ Tried; it changed nothing visible (see the correction below). Blasting Charge was then dropped for Sticky Charge.
  - On trigger, a trap's "trigger effect" runs with the trap owner as attacker. An area there centres on the owner.
  - For an area blast use a status: Blasting Charge v3 plants a copy of In Due Course's time bomb.
  - **Correction:** the ghost-unit model change did nothing visible.
    - The visible placed trap is the trap actor named by `FNameParam2` (`ActorAssetTable` → `BP_ENV_co_TrapDamage`; C++ `TrapBase`/`DamageTrap`, skeletal bear-trap mesh plus a destructible mesh). It persists with save data and team, and plays the snap.
    - Bomb and crystal models are static meshes, so the visible trap can only be swapped by authoring a new `DamageTrap` blueprint (Unreal editor with stub classes; not set up). **Update 2026-11-18:** a cooked-asset route without the editor (clone `BP_ENV_co_TrapDamage` with UAssetGUI, swap particles and sound, shrink meshes) is [untested].
    - The `unit_actor` tool works, but a ghost unit isn't the place to use it.
- **Status-executed abilities don't touch terrain [tested]:** a time-bomb blast (`ExecuteAbilityID` of a `DELAY_DAMAGE` status) deals damage but never ignites ground, not even oil, and not with `FORCE_FLAME` + `bIsLandEffectForceTransitionToEndStatus`.

X
