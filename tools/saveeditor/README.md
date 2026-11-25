# TSMod Save Editor

A standalone editor for TRIANGLE STRATEGY (PC, Steam v1.1.0) saves: every value is editable, and every
edit is rated **Safe / Risky / Dangerous** using the game's own tables (your game pak plus the installed TSMod pak).

## Start it
- **Windows:** double-click `TSModSaveEditor.bat`. It looks for Python 3.11 or newer (with Tk, as python.org installs it).
  If there is none, it offers to install the official release with winget (Windows' package manager) or to open
  python.org; then start it again.
- **Steam Deck (Desktop Mode) and Linux:** run `sh TSModSaveEditor.sh` in Konsole (or a terminal), from this folder.
  SteamOS's own Python already has everything needed; nothing to install. On other Linux systems, install your
  distribution's `python3` and `python3-tk` packages.
  - The editor finds the game and its saves in every Steam library (internal storage and SD card). On Linux the game
    runs through Proton, so the saves are in
    `steamapps/compatdata/1850510/pfx/drive_c/users/steamuser/Documents/My Games/TRIANGLE_STRATEGY/Steam/<id>/SaveGames`.
  - Close the game before writing (the editor checks). If Steam Cloud is on for the game, Steam may replace an edited
    save with the cloud copy: keep a backup, or turn Steam Cloud off for Triangle Strategy while editing.
- Without a launcher: `pythonw TSModSaveEditor.pyw` (Windows) or `python3 TSModSaveEditor.pyw`.

No other programs are needed: the editor reads the game's tables with its own pak reader (`tools/tspak.py`; pure
Python, faster with the optional `pycryptodome` package). The first start reads them (under a minute), then caches them
in `tools/saveeditor/editor_data/cache/`. A new TSMod pak is picked up automatically (the cache is keyed by each pak's
size and date).

## Ratings
| Rating | Meaning | Examples |
|---|---|---|
| ● Safe | consistent with the game's rules | gold, item counts up to 99, a unit's own class or learnable move |
| ● Risky | legal but unusual or untested | level above 50, stats (the game recomputes them), a move outside the unit's kit, more than 7 learned moves, any story flag or script variable, the story position |
| ● Dangerous | likely to crash the load or corrupt the save | an id no table has (a known load crash), negative values, a story position that doesn't exist, clearing the story flags |

Dangerous edits ask before they apply. The **Issues** tab is the legality report for the whole save (unit records,
items, story, every id anywhere in the file including saved battle state), with **Fix** for the common problems.

## Tabs
- **Overview:** leader, location, play time and story chapter (names are shown in English even for a save made in another language, using the game's own text), gold, the Scales of Conviction (Liberty, Utility, Morality), and every script variable.
- **Units:** all unit records. Level, EXP and stats; class and weapon (lists show the unit's own classes and weapon line);
  learned moves (learn from the unit's class tables and weapon trees, or type any id; unlearn); **Add unit from another
  save** copies a unit record from a save that has one (the existing-save delivery path for recruits).
- **Units, more:** **Learn all qualifying moves** (the game never grants learn-table moves from below a unit's level
  after the fact); **Promote… / Demote** along the unit's class chain; the **weapon tree** (bought nodes, with **Un-buy**;
  buying stays in the game); equipped accessories (shown); **Export / Import unit** (a `.tsunit.json` file, to copy a
  built character between saves); **Add TSMod recruits…** (adds every recruit of the installed TSMod pak that the save
  lacks, from game-made level-1 records, pointed at the recruit's own class, weapon and first move: the way to use TSMod
  with a save from before it); **Recruit base-game characters…** (puts the base-game characters this run never
  recruited in the party now, without moving the story. With the option ticked they join like the game's own late
  recruits: raised to the story point's recommended level (Avlora +2), the late recruits promoted to their second
  class, class moves learned. When the story would recruit them later, the game skips it because they're already in
  the party, as on New Game+, where everyone starts in the party. Characters who left through the story aren't listed).
- **Overview, TSMod (needs the TSMod pak):** the **TSMod options** box (the **Fast Chapter 1 battle** switch, Safe) and
  the recruit buttons:
  - **Add TSMod recruits…** (as on the Units tab);
  - **Remove TSMod recruits…**: a checklist; the picked characters' records leave the save (level, class, moves,
    weapon, tree purchases, squad). Equipped accessories stay in the inventory, unequipped. "Back up the picked
    characters first" is on by default. Risky. A removed recruit stays gone, even with the pak installed, until
    restored or re-added;
  - **Scrub TSMod data…**: the path back to a vanilla-friendly save. Backs up every recruit, removes them all, clears
    every other TSMod setting the save holds (the fast Chapter 1 switch), then checks the save against the vanilla game
    data only and says whether any id the vanilla game lacks is left. Then remove `TSMod_P.pak` to play without TSMod
    (one in-game proof of that path is still to do);
  - **Back up recruit data…**: one `.tsrecruit` file per picked character (default folder
    `editor_data/recruit_backups/`);
  - **Restore recruit data…**: puts backups back, into the same save or another one (replaces the character if the
    save has them, otherwise adds them); an equipped accessory comes along (the save's count is raised if it owns
    fewer than its units wear). A backup from another save format version is Dangerous.

  Remove, Restore and Scrub refuse a Continue save (a suspended battle) and any save that names TSMod ids outside the
  recruit records: load it, leave the battle, save to a slot, and edit that. Nothing is written until **Write to slot**.
- **Overview, Export crash logs…** (no save needed): pick crashes from the game's `Crashes` folder (next to the save
  folder; newest ticked) and save one zip: each crash's `CrashContext.runtime-xml` with machine, login and account ids
  and the Windows user name removed, its `UE4Minidump.dmp` if ticked (a memory snapshot, not cleaned), the TSMod log
  (`TSMod_log.txt` / `.old.txt` from the game's folder, cleaned the same way) and `info.txt` (TSMod pak hash, editor
  version, Steam build). Read-only on the game; nothing is sent.
- **Items:** battle items, materials, class medals, accessories, notes: change counts, add, remove.
- **Shop:** shop and quartermaster stock; set any row, or **Restock all sold-out** (sold-out items become buyable again).
- **Quietus:** the Quietus orders in the save; add or toggle them.
- **Unlocks:** mental mock battles (cleared on Normal / Hard) and character-story episodes.
- **Story:** the current story position, and **Go to this story point** from a tree of every chapter, part and story
  point (grouped by the game's own chapter titles). Only points with their own world-map marker can be picked (the
  others are grey: they play on their own and would leave an empty map). The editor then:
  - sets the story position;
  - puts that point's marker(s) on the world map (both marker lists the save stores; character-story markers stay);
  - makes the save resume on the world map;
  - clears the story flags that belong after that point (route-aware). Earlier flags, choices and votes stay;
  - sets the load-screen chapter title.

  It shows what it will change before it applies. Going back along the run's own path is **Risky**; onto a branch the
  run didn't take or another route is **Dangerous**. Tested in game: back to right before the Chapter 17 regiment split.
- **Jump forward (experimental)** (a story point ahead of the save opens this dialog instead): pick how each branch
  on the way goes
  (the votes and the exploration outcomes that change the route; defaults = the save's own values where they lead
  there), optionally keep everyone currently in the party (the story has some leave for a while: Roland leaves after
  the Chapter 1 battle and rejoins in Chapter 2), recruit characters the run never had and raise the party to the target's recommended level
  (class moves up to that level are taught). The editor then replays, in story order, what the game's scripts write at
  each story point on the way: markers done, chapter parts started and ended, scene flags (world-map changes such as a
  destroyed bridge), party joins and departures, outfit sets, the chapter's shop lineup and the branch values; then
  the story warp above. Checked offline against a real playthrough (Chapter 1 to Golden Chapter 19): 184 of 190 story
  flags, every branch value and the main cast's outfits match. **Dangerous**; try it on a spare slot.
  **Try a story change on a spare slot first.** After loading, leave the encampment to reach the world map.
  The flags list is grouped by chapter (with how many are set), searchable, and toggles a flag with a double-click.
- **Issues:** the legality report (above).
- **Backups:** every write and restore first copies the whole save folder to `editor_data/backups/<time>/` with SHA-256
  checks. The last 40 are kept; **Pin** keeps one forever; **Restore** puts one file back (game closed, folder backed up first).
- **Compare:** every difference between the open save and another slot, a backup or a file (overview, story flags,
  script variables, units, items, Quietus, shop), with a filter.
- **Changes:** what you've edited since opening the slot. **Undo / Redo** (Ctrl+Z / Ctrl+Y) step through edits.
- Hover any row for what its rating means. The Overview says whether the installed TSMod pak has every TSMod id the
  save uses (if not, the save probably needs another TSMod version).

## Writing
- Pick a save in the **Slot** list (it starts on "Select a save file…").
- **Write to slot** writes the open save back to its slot; **Copy to slot…** writes it into any other of the game's 10
  slots, empty ones included; **Save copy as…** writes outside the save folder (never into a game save folder).
- Writes are refused while the game is running. Each write: the new bytes are parsed fully first, then the whole save folder
  is backed up, then the file is replaced and re-read.
- **Slot 1 is locked.** It opens normally, but writing it needs a confirmation and typing `UNLOCK`, every time.

## Limits (as of 2026-11-20)
- Only points with a world-map marker of their own can be story-warp targets.
- A forward jump replays what the game's scripts write along the way (see **Jump forward** above), not everything a
  real playthrough does: conviction, items, gold, talk and tutorial flags, in-scene dialogue choices and the early
  feature unlocks (shops, blacksmith; all by Chapter 3) are not replayed. Script steps under conditions the editor can't
  read are skipped. Rated Dangerous: use a spare slot.
- Unit identity edits (class, weapon) change the ids in the record; weapon-tree purchases stay with the old weapon id.
- Kudos: not located in the save yet (needs one known in-game value to search for).
- Weapon-tree nodes and accessories can't be added by the editor: each has a type-specific record layout. Buy or equip
  them in the game; the editor can un-buy nodes and shows accessories.

## Internals
`model.py` (parse and edit; s1 is walked part by part up to the unit array, which `tools/tsunits.py` handles, then the world
tail, script variables and flags), `tables.py` (pak tables via tools/tspak.py), `checks.py` (ratings), `story.py` (anchors; data in
`story_data.json`, generated from the game's exe enum and `Progress/DebugResetAnchor.lua`), `safety.py` (backups, lock,
writes), `app.py` (Tkinter UI). Test hooks: `TSMOD_EDITOR_SAVEDIR`, `TSMOD_EDITOR_DATA`, `TSMOD_EDITOR_PAKS` point the editor
at copies. Format notes: `SAVE_FORMAT.md`.

- **Golden Route Regiment Leader** (Units tab): the squad a unit joins at the Chapter 17 split (None / Benedict / Roland / Frederica). For TSMod recruits the mod keeps this choice; None means the default squad.
