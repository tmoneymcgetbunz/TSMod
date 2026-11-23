# TSMod: recruit Triangle Strategy's named characters

A mod for **Triangle Strategy** (PC / Steam, v1.1.0) that turns 20 of the game's named NPCs and bosses into
permanent members of your army. Each one has:

- **three classes**, promoted with the usual medals, with their own learned moves;
- **their real moves from the game**, under their own names, plus new abilities that fit the character;
- **a weapon with an upgrade tree** and a **weapon skill** of their own;
- stats balanced to sit alongside the main cast, and their own battle and menu sprites (mounted ones included).

| Recruit | Classes | Weapon | Weapon skill |
|---|---|---|---|
| Booker | Poisoner → Venomist → Master Poisoner | Emperor's Sting | At Your Service |
| Clarus | Magnate → Trade Magnate → Consortium Grandee | Brokker's Bargain | Smuggle |
| Dragan | Flame Wielder → Ash Scholar → Ember Sage | Tome of Cinders | Ignite |
| Erika | Bomber → Flame Bomber → Grand Bomber | Aesfrosti Fang | Smoke Bomb |
| Exharme | Swordsman → Swordfighter → Swordmaster | Emerald Serpent | Rouse Troops |
| Gustadolph | Frostruler → Frost Archduke → Sovereign of Winter | Frostruler's Edge | Fire the Deathsknell |
| Idore | Priest → High Priest → Demigod | Divine Ruler | Puppet Master |
| Jerrom | Lancer → Rosellan Lancer → Lance Master | Heartpiercer | Uprising |
| Kamsell | Master Lancer → Lord Lancer → Minister of Order | Lance of the Saintly Seven | Summary Judgment |
| Landroi | Archer → Falkes Archer → Bow Lord | Crown's Bow | Heroic End |
| Lyla | Great Caster → Chrono Caster → Overseer | Scepter of the Ministry | Stop Time |
| Patriatte | Marksman → Royalist Marksman → Lord Marksman | Sovereign Fox Bow | Patriatte's Gambit |
| Plinius | Cryomancer → Frost Scholar → Ministry Savant | Staff of Inquiry | Cryostasis |
| Rufus | Staffwielder → Cudgel Fighter → Cudgel Lord | Brigand's Maul | Knock Back |
| Silvio | Artificer → Master Artificer → Lord of Telliore | Edge of Restoration | Embezzle |
| Sorsley | Shortsword → Dagger Fighter → Minister of Salt | Sorsley's Seal | Salt Tax |
| Svarog | Iron Fighter → Iron Master → Iron Lord | Magma Hammer | Eruption |
| Sycras | Staffwielder → Cudgel Fighter → Cudgel Master | Warden's Cudgel | Crackdown |
| Symon | Divine Blade → Exalted Blade → Divine Hero | Exalted Greatsword | Under Conviction's Banner |
| Thalas | Windcaster → Gale Minister → Prime Minister | Peafowl Ascendant | Gale of State |

Full kits (every move, stats, weapon trees): [docs/CHARACTERS.md](docs/CHARACTERS.md).

## Install
1. Download `TSMod_P.pak` from the [Releases](../../releases) page.
2. Close the game. In Steam, right-click Triangle Strategy → Manage → Browse local files, and open
   `TRIANGLE_STRATEGY\Content\Paks`.
3. Copy `TSMod_P.pak` into that folder, next to `TRIANGLE_STRATEGY-WindowsNoEditor.pak`. Keep the name as it is.

**Back up your saves first** (`Documents\My Games\TRIANGLE_STRATEGY\Steam\<id>\SaveGames`).

## Getting the recruits
- **New Game:** nothing else to do. All 20 join right after the Chapter 1 battle (when Anna joins), at the level the
  game gives its own late joiners.
- **New Game+:** being confirmed.
- **A save started before installing the mod:** the game only creates character slots at New Game, so these saves need
  the recruits added once with the included save editor (`tools/saveeditor`, "Add TSMod recruits to this save"; it
  backs up your save folder first). They then join at the next story scene or world-map visit.

## Cut-content battles
Nine battles the developers drafted and cut are playable from the **Story Battles** list, marked "(Cut Content)":
the Chapter 2 Tourney Final, three duels (Benedict's, Frederica's and Roland's Defiance), a draft of Routing the Roselle,
a test version of the Norzelia River battle, and early versions of the Idore, Lyla and final battles. They're listed from
the start, so their titles can spoil the story. Clearing one gives its rewards but no crown. Details:
[CUT_CONTENT.md](CUT_CONTENT.md).

## Good to know
- A save that contains the recruits needs the pak installed to load. Don't remove the pak while you play such a save.
- To uninstall, delete `TSMod_P.pak` and play saves made before installing (or a backup).
- Recruit weapon trees cost gold only (the game's Materials screen has room for a fixed number of characters).
- Golden route: at the Chapter 17 three-squad split, the recruits join the squads automatically (a balanced default).
  The save editor's "Golden Route Regiment Leader" setting picks a different squad for any of them.
- Exharme and Clarus are shown on foot in the roster and smithy lists; they ride in battle and in the detail menus.

## Save editor
`tools/saveeditor` is a standalone editor for Triangle Strategy saves. Every value can be edited, and each edit is rated
Safe / Risky / Dangerous from the game's own data; it backs up before writing and will not write while the game is
running. It runs on Windows and on Steam Deck / Linux (Desktop Mode). Requirements and usage:
[tools/saveeditor/README.md](tools/saveeditor/README.md).

## For modders
- [SYSTEMS.md](SYSTEMS.md): how the game's battle data, AI, sprites, maps and scripts fit together, and what can be modded.
- [SAVE_FORMAT.md](SAVE_FORMAT.md): the save file format (encryption, unit records, learned lists, weapon purchases).
- [CUT_CONTENT.md](CUT_CONTENT.md): cut and unused content found in the game files (battles, scenes, abilities, the debug menu).

Claims in these docs are tagged **[tested]** (proven in game), **[read]** (read from game data or scripts),
**[community]** (reported by other modders) or **[inferred]**.

## Building from source
The repository holds the mod sources (`mods/`: data edits as JSON, Lua hooks) and the tools that build them
(`tools/`). Data tables and scripts are read from your installed game at build time. A few edited game assets are
included because the build packs them as they are: the cut battles' six levels (`mods/cut_battles/maps/out/`) and
Dragan's trap actor and actor table (`mods/dragan_trap/src/`). The game's Lua XOR key (`lub_key.bin`) is included too.

Requirements:
- Python 3.11+ with `pycryptodome`.
- [repak](https://github.com/trumank/repak) as `tools/repak/repak.exe`.
- A Lua 5.1 compiler as `tools/lua51/luac5.1.exe`.
- The game's Lua scripts, in three forms the build uses:
  - extracted from the game pak, still encrypted, into `extracted_lub/` (`python tools/tspak.py extract <game pak> extracted_lub LuaScriptBin`);
  - decrypted with `tools/lubcrypt.py dec` (it uses the 256-byte XOR key `lub_key.bin` in the repository root);
  - decompiled with [unluac](https://sourceforge.net/projects/unluac/) into `decompiled/`, keeping the layout below `LuaScriptBin/Src/`.
    The Lua hooks are appended to these sources.
- The game's data tables as JSON (`python tools/dump_tables.py`, into `data/tables/`) if you regenerate a recruit
  with `tools/gen_recruit.py`.

If the game isn't in a standard Steam folder, set `TS_PAKS_DIR` to its `Content\Paks` folder. The full release pak:

```
python tools/build_mod.py mods/recruit_*_full mods/join_release mods/ch17g_split mods/dragan_trap mods/landroi_heroic_end mods/b2_hooks mods/c_hooks mods/d_hooks mods/cut_battles mods/npc_prohibit mods/fast_ch1 mods/unlock_repair mods/release_log --name TSMod --out build
python tools/verify_stage.py build
```

## License
The mod's code and data edits are MIT-licensed ([LICENSE](LICENSE)). Triangle Strategy and its assets belong to Square Enix.

## Credits
Thanks to the Triangle Strategy modding community for the groundwork this builds on, and to the authors of
[repak](https://github.com/trumank/repak), [UAssetGUI](https://github.com/atenfyr/UAssetGUI) and unluac.
Triangle Strategy is © Square Enix. This is an unofficial fan project, not affiliated with or endorsed by Square Enix.

---
<sub>Made with AI assistance (Claude, by Anthropic), used for research, tooling and code; design decisions and
in-game testing by the author.</sub>
