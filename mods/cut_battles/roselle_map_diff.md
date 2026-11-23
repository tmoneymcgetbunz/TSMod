# Roselle draft vs the shipped Rosellan Village battle: full map diff (2026-11-21) [read]

Compared: the cut draft `Map/Story/ms12_x23/ms12_x23_battle_01` with the shipped Chapter 11 battle "Routing the Roselle"
`Map/Story/ms11_x20/ms11_x20_battle_01`, at all three layers. Tools: UAssetGUI JSON (`maps/src/*.json`), `tools/wbmap.py`,
`maps/grid_diff.py` (baked grid, partial decode).

## 1. Level file (what gets loaded)
| | Draft (ms12_x23) | Shipped (ms11_x20) |
|---|---|---|
| Terrain sublevel | `A1_EX_Villagesano_WB` (a developer's whitebox copy) | `A1_EX_Village_WB` |
| **Art sublevel** | **none** | `A1_EX_Village_GFX` |
| Props/other sublevel | **none** | `A1_EX_Village_B_OTH` |
| Stand-by area | `X_StandBy_GFX/OTH/WB` | same |
| Extra | `SkySetLevel_Dummy`, `WorldMapLevel` (removed in Test 41b) | none |
| AI-zone markers | 2 (`AISetting1`, `AISetting2`) | 8 (`ROOF`, `Right_Wing`, `Left_Wing`, `RIGHT_ARCHER`, `LEFT_ARCHER`, `BOSS`, `AI_Normal`, `AISetting2`) |
| Camera presets | none | 4 view presets on the level script |
| Battle grid | `WBAsset/ms12_x23/ms12_x23_battle_01` | `WBAsset/ms11_x20/ms11_x20_battle_01` |

So the draft loads **no art at all**: only the whitebox blocks. It is also the only one of the six cut levels with no art
sublevel; the other five stream one (the Tourney and river levels, which now load, each have a `_GFX`).

## 2. Terrain (whitebox blocks, `tools/wbmap.py`)
- Same 19×19 footprint, same layout (cliffs, houses, paths): **249 of 361 cells identical**.
- 112 cells differ, almost all in labelling: the draft marks everything walkable as SOIL, where the shipped map has
  75 ROOF, 13 FLOORING and 10 STONE cells (rooftops, floors, paving). One SOIL cell became an OBSTACLE.
- 13 cells differ in height, mostly the path at x 7–8, y 5–9 (draft 12/8, shipped 13), and two at y 10 (8 vs 7).
- Conclusion: the draft terrain is an **earlier pass of the same village**, not a different map.

## 3. Baked battle grid (`WBAsset`, what the battle actually uses)
- Both: version header, 21×21 grid, 441 cells, **799 terrain layers**.
- **643 of 799 layer records are byte-identical**; the rest are the same roof/floor/stone tagging and height changes.
- A third grid, `WBAsset/ms11_x20/ms11_x20_battle_sanotest` (the "sano" developer's test grid), is a different, later
  iteration (1,115 layers, with walls), not the draft's source.

## 4. Draft unit positions on the shipped map
All 13 enemy/guest spawns and all 16 deployment squares land on walkable tiles of the shipped grid (none blocked). Five
spawns would stand on roofs or floors instead of "soil", and three on the raised path (height 13 instead of 8–10).

## What this means
- **Textures:** the draft streams no art layer, so even when it loads it would show only grey whitebox blocks
  [inferred from the sublevel list].
- **The hang:** the draft is the only cut level with no art sublevel. Whether that is why it still hangs is unproven
  [inferred]; the Test 41d log lines are meant to tell.
- **Option:** switch the draft onto the real village: stream `A1_EX_Village_WB` + `_GFX` + `_B_OTH` and use the shipped
  grid `ms11_x20_battle_01`. The draft's own script, units, rain/storm, barricade events and dialogue stay; its positions
  all fit. It loses only the draft's few height tweaks and its untagged roofs.

## Decision (user, 2026-11-21)
Use the real map: done in `maps/fix_levels.py` (Test 41e).
