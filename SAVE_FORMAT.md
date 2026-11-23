# Triangle Strategy (PC) save format

Status 2026-11-16: **decrypt and re-encrypt work and are verified**. All 4 of your save files decrypt with matching SHA-1, and re-encrypting gives byte-identical files. Tool: `tools/tssave.py`.

Credit: the cipher and the outer layout were first documented by the community editor [ShaneQi/triangle-strategy-save-editor](https://github.com/ShaneQi/triangle-strategy-save-editor) (`public/lib/core.js` header). `tssave.py` is an independent Python implementation of that description. The unit-record findings below are new.

## Layers

1. **GVAS** (Unreal SaveGame) container, UE 4.27, 58 custom versions. Class `/Script/Newera.SaveGameData` (slots, autosave, continue) or `SaveSystemData` (settings). It holds a single property, `bulkData`: `ArrayProperty<ByteProperty>`, followed by `None` and 4 zero bytes.
2. **NWER blob** (= bulkData):

   | Offset | Contents |
   |---|---|
   | 0x00 | `NWER` |
   | 0x04 | u16 version (57 for your saves) |
   | 0x06 | u16 = 1 |
   | 0x08 | u8 kind (0 system, 1 game) |
   | 0x09–0x0B | flags (0x0A differs per slot type: 00 slot, 01 autosave, 02 continue) |
   | 0x0C | 20-byte SHA-1 of `plaintext[0x40:-20]`. **This is also the key** |
   | 0x20 | 32 zero bytes |
   | 0x40 | ciphertext. The plaintext ends with the same SHA-1 |

   Cipher: a 256-byte substitution table T, built by 128 rounds of swaps keyed on the SHA-1. Then `c[i] = T[p[i]] ^ K[i % 20]`, with `i` counted from 0x40. It's self-keyed and self-checking: change the plaintext and `encrypt` recomputes the SHA-1 and re-keys.
3. **Game-data plaintext** = 0x40 header + three `int32 length + bytes` sections + SHA-1:
   - **s0, slot preview:** saved-at (FDateTime ticks), play time in seconds, leader level (u16), a byte, leader name, location label, thumbnail (BGRA), title strings. Your slot 1: saved 2025-07-14 16:39, **186h 45m**, Lv 50, leader Serenoa.
   - **s1, game state** (620 KB in your save): 24 serialized parts (story chart, choices, convictions, inventory, units, flags, money …). The editor's `s1parse.js` maps them all.
   - **s2, field/battle state** (current map, camera, scene).

## s1 part map (2026-11-19)
**[community]** ShaneQi's save editor (read for reference only; no code copied) parses all of s1 by translating the exe's own serializers (`FUN_140d3c7e0` and children; verify in our Ghidra project before relying on one). Order:
1. story chart: `TMap<FName, 4 bools>`;
2. dialogue choices: `TMap<FName, bool>`;
3. vote events;
4. **convictions** (2× int32[4]);
5–14. small blocks: pickups, location, map actors, name flags;
15. place emblems;
16. unit data;
17. **inventory**: `TMap<FName,int32>` ×2 or ×4 by version (items, materials, medals);
18. **accessories**: 5 maps;
19. battle orders;
20. **shop stock**;
21. seen list (notes, stories, tutorials);
22. counters (achievement counters; #40 = total gold earned);
23. **units** (our unit records);
24. world tail: leader name, **gold** (int32).

After those parts come the map/battle state, camera, world-map state, then the two name-keyed tables below. FNames are serialized as FStrings in this archive.

**Script variables and story flags are saved by name [read in our save, 2026-11-19].** Both tables are written by walking a reflected enum:
- **Script variables** (`ELuaSysGlobal`): an int32 count (= enum entries), then `{FString name, int32 isString, int32 | FString}` for indices 1..count-1. 47 entries in a v1.1.0 save:
  - story position (`SCENARIO_ANCHOR` = 462);
  - vote results (`VOTE_MS03_H01`…);
  - battle scratch values;
  - level and music strings.
- **Story flags** (`ELuaFlag`): an int32 count (2362), then `{FString name, int32 value}` for flags 1–2361 (894 on in that save). Then:
  - an FString ("Voting Results");
  - a `TArray<FString>`;
  - an int32;
  - a `TMap<FString,FString>` (empty; purpose unknown).
- **Consequence for TSMod options:** flag numbers above 2361 are **not saved**, because there is no enum name to write. So flags above 2361 can't hold mod state.
- **Candidate persistent slots [inferred, need a probe]:**
  - script variables that no shipped Lua uses: `ELAPSED_TIME_PER_WORDS`, `PLACENAME_INDEX`, `MS10B_X19_JUDGE` (32 bits each; check the exe doesn't write them);
  - test flags only dev scripts touch: `TEST_FLAG` (2), `EVENT_TEST_BURNED_DOWN` (2159), `WI_END_DEBUG_SCENARIO` (933);
  - the empty `TMap<FString,FString>` if Lua can reach it.

## TSMod save state (keep in step with `tools/saveeditor/recruit_tools.py` `TSMOD_FLAGS`)
Everything TSMod can leave in a save [read 2026-11-23, every TSMod id searched in the saves]:
- the 20 recruits' unit records (all their TSMod ids: param, class, weapon, moves, weapon skills, tree nodes);
- `TEST_FLAG` = 1 when the fast Chapter 1 switch is on (`mods/fast_ch1`).
- Cut battles (`mods/cut_battles`) leave **nothing** in normal saves [read: every cut row id searched in saves made after playing them]. Only a battle suspended mid-fight (`ContinueSaveData`) names its quest and battle-info ids (`QUEST_INFO_TSMOD_CUT_*`, `BATTLE_INFO_SITUATION_TSMOD_CUT_*`); the editor refuses Continue saves, so Scrub has nothing to remove for them.
Nothing else: dialogue-history blocks naming NPCs and outfit-set entries are vanilla rows. A battle saved mid-fight
(Continue save, header byte 0x0A = 2) can also name deployed recruits; the editor refuses those. The one id outside the
vanilla tables that vanilla saves also hold is `BATTLE_ABILITY_AUTO_HEAL_TOUGHNESS` (vanilla orphan). The editor's
**Scrub TSMod data** removes both and checks the result against the vanilla tables.

## Unit records (new findings)

- Each unit record starts with the unit-master `FString`. **The 16-int32 stat block sits exactly 83 bytes after the string's length field + 3**, verified on all 31 units seen. Order: `level, exp, move×100, jump up, jump down, HP, TP, speed(f32), TP/turn(f32), STR, INT, DEX, AGI, LUK, DEF, MDF` (STR..MDF order from the editor's notes). These are copies of the growth-table row; the game recomputes them on level-up, class change and battle entry.
- **A New Game pre-creates unit records for all 30 recruits** (Lv 1, unjoined ones included). Joining doesn't create them.
- **A non-original recruit gets a record added on `JoinParty`.** The test autosave has `UNIT_MASTER_CH_N106` (Sycras) with Lv 2, EXP 10, HP 96, Str 8, matching the in-game screens. So the save format needs no special support for new recruits.
- Fixed 29-entry list of `P002…P030`, each with 4 bytes `[flag, flag, flag, index]`. In the completed save all flags are `01 01 01`. Probably a met/recruitable status table. Sycras isn't in it, yet he shows in the Roster, so the Roster doesn't depend on it.
- A short list (`P001–P005 + N106` in the test save) looks like the current team/deployment list.

- **Unit array (2026-11-16):** an int32 count followed by contiguous records sorted by unit-master id. Each record starts with its unit-master FString. Sizes: about 590 bytes at Lv 1–2, 2.4–3.1 KB late game. The array is followed by the world tail: leader-name FString, then **gold (int32)**.
- **`JoinParty` can't create a record.** It returns false for a unit with no record. Records are made only at New Game, for every growth unit at that time. To add a new unit to an existing save, use `tools/tsunits.py inject <target> <template> <UNIT_MASTER_ID> <out>`, which copies a record from a save that has one.

- **Learned abilities and passive cache.** Near the end of a record:
  - A learned-ability list: an int32 count, then per ability an FString plus small ints.
  - Then the count of a **passive-effect cache**, then its entries. Each entry is the support ability plus derived ids (`CorrectParam`, `FNameParam1`, …), and the layout varies by ability type.
  - Then the class id.
  - Removing a fill-in from a recruit's learn table doesn't remove it from existing records. `tsunits setstr --first` repoints the learned-list entry (it comes first). The cache entry is left alone; whether the game rebuilds it is untested.

**Implication for mods:** a save made while an NPC-recruit mod is installed contains that NPC's record. Loading it **without the mod** may fail or misbehave, because the unit's battle param and class don't exist in vanilla data. Keep mod-test saves in their own slots.

## Using the tool (always on copies)

```
.venv/Scripts/python tools/tssave.py summary  <file.sav>            # preview + every unit's level/EXP/stats
.venv/Scripts/python tools/tssave.py decrypt  <file.sav> <out.bin>   # plaintext (SHA-1 verified)
.venv/Scripts/python tools/tssave.py encrypt  <template.sav> <plain.bin> <out.sav>
```

`encrypt` writes a **new** file; it never touches the game's save folder. 

## What this enables next

- **Diffing** two decrypted saves (before/after one action) to map unknown fields: flags set by a scene, what `JoinParty` writes, etc.
- **Test states from your completed save:** e.g. a copy with a different story anchor, or a modded NPC already in the roster at Lv 50, for testing late-game content without replaying.
- **Validating mods:** confirm what a recruit mod actually wrote to a save.

## Learned list and weapon purchase blocks [read]
- **Learned-ability list:** int32 count, then per entry `[i32 flag][i32 0][u8 0][FString ability]`.
  - The flag's meaning is unknown: 1 on every Resist and most passives, 0 on most commands, and Sycras's Detain (a command) has 1.
  - `tsunits.py learned` prints the list; `addlearned` appends to it. Use it for learn-table entries below the unit's current level, since the game doesn't grant those retroactively.
  - The passive-effect cache follows, and the game ignores it for effects (stale `TP_PLUS`/`AUTO_HEAL` entries on a unit without those moves did nothing, and the record loaded fine). Each entry is `[i32 0][FString ability][payload]`, the payload written by the ability class's own serializer: about 45 shapes in real saves (strings, ints, floats, nested ids), so the save editor never edits the cache; unlearning changes only the learned list.
    - Layout [read]: int32 count, then per entry `[i32 0][FString ability][i32 0][FString CorrectParam]`. Example: Svarog's Fireproof is `BATTLE_ABILITY_INVALID_FLAME` → `BATTLE_CORRECTPARAM_ABILITY_INVALID_FLAME`.
    - `tsunits.py removelearned` drops an ability from both lists (for kit changes). `addpassive` adds a cache entry so a patched record mirrors a real one.
- **After each weapon FString:**
  - Before any purchase, 12 zero bytes, then the next field (`01 00 00 00 05 'None'`).
  - A **weapon-skill** purchase (`bIsWeaponAbility`) writes `0, 0, [count 1: id, 1, 0, id, 0]`. This is the special-ability list, and the battle menu lists it unfiltered.
  - A **tree-passive** purchase on that rank wrote `1, 0, id, 0, 1, id, 0`.
  - Resetting to the 12 zero bytes loads fine and un-buys the rank's nodes.
  - Un-registering just the weapon skill: replace `count 1 + {FString id, i32 1, i32 0, FString id, i32 0}` with `count 0`. Needed whenever that ability's class changes.

## Save editor parse (2026-11-20) [tested on 5 saves, byte-identical round-trips]
`tools/saveeditor/model.py` walks s1 part by part to the unit array (our own code from the field order above), and checks it lands exactly where `tsunits.records` finds the array. Located and editable:
- **Convictions** (part 4, first int32[4]): index = `EFaithType` (1 FREEDOM = Liberty, 2 BENEFIT = Utility, 3 MORAL = Morality; 0 unused) [inferred mapping; values 6608 / 6832 / 6081 in a late save]. The second int32[4] was all 0.
- **The 12 TMap<FName,int32> after the units' preamble**, labelled from their keys: place names; unit attached data ×2; two empty; **notes**; **battle items**; empty; **materials**; **class medals**; **accessories**; empty. Then the Quietus orders `{id, int32, bool}`.
- **Unit identity bytes** (record offset 46–51 at Lv1, after the unit-master and a 'None' FString): 46 = `ECharacterId`, 47 = `SpriteType` (`ENeweraFlipbookOverrideType`), 48 = `FootstepType`, 49 = `ActionVoiceType`, all from the unit-master row; 51 = unknown (29 for most). The editor adds recruits from game-made Lv1 records (`tools/saveeditor/recruit_records.json`) instead of building these.
- **Weapon tree** [read, 50/50 units parse]: after the unit's weapon FString: int32 N, then N bought-node objects `{int32 0, FString node id, type-specific payload}` (e.g. a stat node: `0, CorrectParam`; a range node: `0, id, 1, target, 1, 4, 0, 1`), then the same N ids as `TArray<FString>`. Un-buying one node = remove its object and its echo entry and decrement both counts [tested on copies: re-parses].
- **Equipped accessories:** `BATTLE_ACCESSARY_*` FStrings in the record (with `BATTLE_ABILITY_ACCESSARY_*` for those with an effect).
- **Shop stock table:** the longest run of `{FString item, int32 stock, 6 bytes}` containing `ITEM_CLASSMEDAL_MIDDLE` (the id also appears in the inventory, so every occurrence is tried); 191 rows in a late save; an item can appear twice.
- **Mental mock battles:** `GOP_Quest_Info.ClearFlag_Normal / _Hard` name story flags (`QUEST_CLEAR_NORMAL_nn`). Character stories: `WI_END_CSnn_Enn(_EX)` flags.
- **Uncollected gold bags are not paid at battle end**, so they aren't in the save.
- World tail (leader name, gold), the script variables (found right before the flag table) and the flag table.
- **Id scan fix:** the id pattern needs a left boundary. Without it, `NOTE_NOTE_KEYITEM_SOLT` produced a false `ITEM_SOLT` (and `ITEM_FLAG_10…60`, `ITEM_ORLAYA_NOTE`, …), which `tsunits ids` reported as "vanilla leftovers". Both tools now use `(?<![A-Z0-9_])`; the only real vanilla orphan is `BATTLE_ABILITY_AUTO_HEAL_TOUGHNESS`.

## Party state [read, 2026-11-22]
- One byte, 7 bytes before the end of each unit record: 0 = never joined, 1 = in the party, 2 = left (the game's `EPartyMember`: Outsider / In / Out; memory +0x445, which the battle unit list reads). `JoinParty` sets 1, `LeaveParty` 2. Seen in natural saves: Roland 2 after he leaves in Chapter 1; every member 1 at Golden Chapter 19.

## Golden-route squad [read]
- One byte, 6 bytes before the end of each unit record: 0 = none, 1 = Benedict's squad, 2 = Roland's, 3 = Frederica's. Set by the Chapter 17 split; read by `GetPartyTeam`. It survives into New Game+ until the next split rewrites it.
