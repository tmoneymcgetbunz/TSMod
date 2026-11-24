# TSMod: new recruits, cut battles and a save editor for Triangle Strategy

A mod for **Triangle Strategy** (PC / Steam, v1.1.0) with three parts:

- **20 new recruits:** named characters and bosses from the story join your army for good.
- **9 cut-content battles:** battles the developers drafted and cut, restored and playable.
- **A save editor:** edit any value in a save, with every edit rated Safe / Risky / Dangerous.

## The recruits
Booker, Clarus, Dragan, Erika, Exharme, Gustadolph, Idore, Jerrom, Kamsell, Landroi, Lyla, Patriatte, Plinius, Rufus,
Silvio, Sorsley, Svarog, Sycras, Symon and Thalas.

Each one fights with their own moves from the game, plus new abilities that fit the character. They promote with
medals like the main cast and have their own weapon, upgrade tree and weapon skill. Their battle and menu sprites are
their own, mounted ones included. Every recruit's classes, moves, weapon tree and stats: [characters/](characters/README.md).

- **New Game:** nothing to do. All 20 join right after the Chapter 1 battle (when Anna joins), at the level the game
  gives its own late joiners.
- **A save started without the mod, or a New Game+ from one:** the game only creates character slots at New Game, so
  add the recruits once with the save editor ("Add TSMod recruits"). They join at the next story scene or world-map
  visit, at the same level a New Game would give them.
- **Golden route:** at the Chapter 17 three-squad split, the recruits join the squads automatically. The save editor
  can move any of them to another squad.

## Cut-content battles
Nine battles found in the game files, playable from the **Story Battles** list with "(Cut Content)" in the title:

| Battle | What it is |
|---|---|
| The Tourney Final | A final round cut from Chapter 2: Serenoa and Roland face Maxwell and Julio for the title. |
| Roland's Defiance | A cut Chapter 17 duel: when the vote favours Benedict's plan, Roland stands against Serenoa one on one. |
| Frederica's Defiance | The same duel when the vote favours Roland's plan. |
| Benedict's Defiance | The same duel when the vote favours Frederica's plan. |
| Routing the Roselle (Draft) | An early draft of the battle against Jerrom: rain, barricades and Rufus at your side, on an older map. |
| The Norzelia River (Test) | A test version of the battle against Avlora's ship: much the same fight, with a plain polygon staircase in place of the boarding mechanic. |
| Fighting Idore (Early) | An earlier battle at the waterfall, with a different Hyzantine force and Roselle fighters against you. |
| Fighting Lyla (Early) | An earlier battle in the streets of Hyzante, with a different enemy force. |
| The Final Battle (Early) | An earlier final battle: Idore and the Hierophant together in the audience hall, surrounded by Automatons. |

They're listed from the start, so their titles can spoil the story. Clearing one gives its rewards but no crown.
What else was cut, and how these were restored: [CUT_CONTENT.md](CUT_CONTENT.md).

## Save editor
A standalone editor for any Triangle Strategy save, with or without the mod. It runs on Windows and on Steam Deck /
Linux (Desktop Mode). Every edit is rated **Safe / Risky / Dangerous** from the game's own data, and Dangerous edits ask
first. Before every write it backs up the whole save folder, and it won't write while the game is running.

- **Units:** level, EXP, stats, class and weapon; learn or unlearn moves; **Learn all qualifying moves**;
  promote and demote; un-buy weapon-tree nodes; export a unit to a file and import it into another save.
- **Recruits:** add the TSMod recruits to any save; remove them; back up and restore a recruit; pick each recruit's
  Golden route squad; **Scrub TSMod data**, which removes everything TSMod added to a save, as a way back to the unmodded game (not yet proven in game).
- **Items and shop:** counts of items, materials, medals and accessories; set shop stock, or restock everything sold out.
- **Quietus and unlocks:** Quietus orders, mental mock battles and character-story episodes.
- **Story:** go back to any story point with a world-map marker, choosing from a tree of every chapter; jump forward
  (experimental), replaying the branches and party changes on the way.
- **Overview:** gold, the Scales of Conviction, script variables, story flags, and a Fast Chapter 1 battle switch.
- **Issues:** a legality report for the whole save, with one-click fixes for common problems.
- **Backups, Compare, Undo:** restore any backup; compare the save with another slot or a backup; undo and redo edits.
- **Export crash logs:** packs the game's crash reports into one zip with your machine ids and user name removed.

Setup and details: [tools/saveeditor/README.md](tools/saveeditor/README.md).

## Install
1. Download `TSMod_v1.zip` from the [Releases](../../releases) page and unzip it.
2. Close the game. In Steam, right-click Triangle Strategy → Manage → Browse local files, and open
   `TRIANGLE_STRATEGY\Content\Paks`.
3. Copy `TSMod_P.pak` into that folder, next to `TRIANGLE_STRATEGY-WindowsNoEditor.pak`. Keep the name as it is.
4. The `SaveEditor` folder can go anywhere. On Windows, start it with `TSMod Save Editor.bat` (it needs Python 3.11 or
   newer and offers to install it); on Steam Deck / Linux, run `sh "TSMod Save Editor.sh"`.

**Steam Deck:** step-by-step guide in [STEAM_DECK.md](STEAM_DECK.md).

**Back up your saves first** (`Documents\My Games\TRIANGLE_STRATEGY\Steam\<id>\SaveGames`).

**Turn off Steam Cloud for Triangle Strategy before editing saves** (right-click the game → Properties → General →
Steam Cloud). Otherwise Steam can replace a save the editor just wrote with its older cloud copy, or upload a modded
save that then needs the pak on every PC you play on.

## Good to know
- A save that contains the recruits needs the pak installed to load. Don't remove the pak while you play such a save.
- To uninstall, delete `TSMod_P.pak` and play saves made before installing (or a backup).
- Recruit weapon trees cost gold only (the game's Materials screen has room for a fixed number of characters).
- Exharme and Clarus are shown on foot in the roster and smithy lists; they ride in battle and in the detail menus.
- **Reporting a crash:** in the save editor, click **Export crash logs…** on the Overview tab and attach the zip to
  your report.

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
