# Cut and unused content: sweep 1 (2026-11-17)

How this was found:
- Every DataTable (2,076, English and Japanese text), all 3,759 decompiled Lua scripts, all 1,310 maps and the exe's strings were indexed.
- An item counts as **unused** when nothing references it from the story scripts, maps, exe, enumerated tables (shops, drops, quests, story chart…) or rows reachable from those.
- **Debug-only** means only debug/test scripts use it.

Labels:
- **[read]**: seen directly in the data.
- **[inferred]**: my interpretation.
- **[ask]**: needs your player-side knowledge.

Not indexed: non-map binary assets (blueprints) and the exe's compiled logic. So "unused" means *unused in data*, not proven unreachable.

Translations of Japanese-only text are mine.

---

## 1. Cut battles and story branches (the big finds)

### 1a. Chapter 2: the Tourney final vs Maxwell [read]
`Scenario/Story/ms02_x02/ms02_x02_battle_02.lua` and map `ms02_x02_battle_02.umap`. Nothing in the story flow loads it.

Setup:
- Serenoa and Roland are forced into the fight.
- Enemies:
  - **Maxwell**, as "BOSS1", using the enemy "Dawnspear" unit N001;
  - **Julio**;
  - 2 archers and 2 swordsmen.
- Enemy level about 40-44, so it's a debug-tuned or late-tuned fight.

Intro dialogue (Japanese only):
- Maxwell: "So you've fought your way up. Are you prepared?"
- Roland: "Yes! I'll fight you as my teacher."
- Julio: "Lord Maxwell, leave clearing the way to me."

Mid-battle lines:
- "Lord Roland, you've grown strong."
- "This is no training session… receive my spear!"
- "I won't let you surpass me so easily. On my name as the Spear Saint!"

Two outcomes, **translated in English**:
- Win: Regna announces "the glory goes to Lord Serenoa Wolffort and his stalwart allies!"
- Lose: "the glory goes to the Dawnspear…"

The death event is a placeholder ("死亡イベント(仮)").

There are also unused alternate results for the *first* Tourney battle. One reads "Victory goes to Minister Exharme Marcial!" (`ms02_x02_battle_01_after_05/06`).

### 1b. Chapter 17: duel the companion you voted against [read]
- **Benedict route, vs Roland:**
  - Roland, having learned "the truth" about royal blood: "A father's love, the trust of retainers, talent… how could you, who has it all, understand!… I always admired you, and envied you… I wanted to beat Serenoa Wolffort!"
  - Serenoa: "As head of House Wolffort, I will cut you down!"
  - Then: "Roland Glenbrook!" "Serenoa Wolffort!"
- **Roland route, vs Frederica:** "You once told me I was a member of House Wolffort… it was a fleeting dream! Let us settle this: whose conviction is right!"
- **Frederica route, vs Benedict:**
  - Benedict defies the Scales and urges Serenoa to use the rock salt to become **King of Norzelia**. He swore to Serenoa's mother, **Lady Destra**, to protect him "whatever it takes".
  - After losing, he asks to be finished off. Serenoa refuses and asks, as his "last request", that Benedict evacuate and protect Wolffort's people while Serenoa heads secretly for Hyzante.
Chapter 17's vote (`ms17_h01`) sets the route: Benedict = 0, Roland = 1, Frederica = 2, Golden (Serenoa) = 3. The progress data wires each route to its own battle:

| Route | Battle | Enemy | Enemy stats |
|---|---|---|---|
| Benedict | `ms17b_x35` | **Roland** | N402 |
| Roland | `ms17r_x36` | **Frederica** | N404 |
| Frederica | `ms17f_x37` | **Benedict** | N403 |

- All three reuse Chapter 7's Wolffort-streets map config (`BATTLE_MAPCFG_MS07_X08`).
- They have turn-by-turn talk triggers, and each has before / during / after dialogue tables.
- **No script references that dialogue.** The battles have no title text and no replay entry.
  - Every other story battle has a replay entry.

Dialogue samples:
- Benedict route (English): Roland: "Have you no shame!?"; Benedict: "Have you? You who would have willingly surrendered his kingdom to Hyzante."
- Roland route (Japanese): Frederica: "Why didn't you choose me?… In the end, you chose your friendship with Lord Roland over me."

**Confirmed cut:** in the shipped game, the Chapter 17 disagreement with the route's opposer is only a short cutscene. These fights are known in the community as replaced. What's left in the data:
- three battle scripts and maps, wired into progress;
- enemy stats for Roland, Frederica and Benedict (N402–N404);
- the dialogue tables:
  - Benedict route: mostly English;
  - Roland and Frederica routes: largely Japanese.

### 1c. An earlier draft of "Routing the Roselle", with a different ending [read]
`ms12_x23`, with battle info, map and scripts, but no replay entry and no title. It's a draft of the battle the shipped game has as `ms11_x20` "Routing the Roselle" (give up the village).
- **Same in both:** Rufus and Jerrom are on the field, and Silvio sides with Wolffort.
- **Different:**
  - The draft sits one chapter later, behind its own Chapter 12 vote. The vote is English, `ms12_h01_vote_start`: "So we continue negotiations with Jerrom, or forcibly send the Roselle to Hyzante?"
  - Its six `ms12_h01` maps are unused.

Draft dialogue (English, with the older spelling "**Jerome**"):
- Before: "Jerome, please don't do this. Lay down your arms…" Silvio: "Now, Rufus! Stand with House Wolffort and bring these filthy Roselle in!"
- After: Jerrom offers his life so the villagers are spared, and Serenoa accepts. Frederica begs them to stop.
  - **Roland steps in and does it himself**: "Allow me to do this, Serenoa… The only one at fault is the cowardly royal family of Glenbrook… I am sorry."

**Shipped flow, from the live dialogue tables:**
- Chapter 11, `ms11_x20` "Routing the Roselle":
  - The fight is stopped.
  - Jerrom agrees to listen for the sake of Frederica's mother, Orlaea.
  - That night he overhears Serenoa and Roland and agrees to gather the villagers.
- Chapter 12, `ms12_x22` "Confronting Silvio":
  - Serenoa keeps his promise.
  - **Jerrom fights alongside you against Silvio and Rufus**, and Silvio dies.

Battle differences (shipped `ms11_x20` vs draft `ms12_x23`) [read]:

| Aspect | Shipped | Draft |
|---|---|---|
| Weather and time | Sunny, noon | **Heavy rain and storm, 8 a.m.**, rain puddles |
| Map | Finished village art | Older whitebox layout `A1_EX_Villagesano_WB`, no art layer; may render untextured [inferred] |
| Ends when | 8 enemies are defeated | Jerrom falls: he kneels, then the after-scene plays |
| Music | Battle track `M25`, plus a "pinch" switch | Opens on story music "Bitter" (`M51`) and switches to the **Climax** battle theme when Jerrom acts |
| Enemies | 14 villagers | 11 villagers, plus **barricades**; two swordsmen change behavior when a barricade breaks |
| Same in both | Rufus as a guest ally; Jerrom as boss (same stats) | |
| Dialogue | 9 talk events | Fewer; turn-1 talks fire if Frederica or Serenoa are deployed |

So the shipped Chapter 12 has no "hand them over" choice. The cut `ms12_h01` vote plus the `ms12_x23` battle were that branch:
- you side with Silvio and Rufus and storm the village;
- Jerrom gives himself up, and Roland kills him;
- in the branch's closing scene (`ms12_x23_c0_0010`), **Idore, speaking for the Pontiff, makes Serenoa one of Hyzante's Seven Saints**. Exharme objects that it's premature; Idore recalls having said the same about Exharme.

### 1d. Chapter 14: a test version of the Norzelia River battle vs Avlora [read]
`ms14_x29_battle_02.lua` and map:
- Avlora as boss (enemy stats N107);
- 9 Aesfrost rank-2 soldiers;
- placeholder field name (`MAP_NAME_B1000`).

Never loaded by the shipped game. Played through TSMod, it is much the same battle as the shipped one, with a plain
polygon staircase in place of the ship-boarding mechanic [tested].

### 1e. Other cut branches and scenes [read]
- **A Chapter 11 bad ending** (`ms11_f02`, Japanese only, never played):
  - **Cordelia** mourns her brother Roland: "Brother… you fought here until the very end. I will carry your regrets. I, too, will now join you…"
  - Narration: the Archduke dies suddenly, and Aesfrost collapses. Duke Svarog is made Archduke, and war with Hyzante follows. It lasts over a century, with "neither victors nor vanquished", and Norzelia becomes a lawless wasteland.
  - Hyzantine soldiers cut Serenoa down ("Is he immortal…?").
  - "That night, the name Wolffort vanished from the map. Whether their deeds were just, later scholars remain divided. But they lacked the strength to bring justice about."
- **Chapter 13 vote reactions from Exharme** (`ms13_h01_vote_120/130`), one per option:
  - Assassination: "You chose the crooked path, Wolffort. You're no better than Aesfrost."
  - Siege and negotiation: "The orthodox path… but mercy may come back to bite you."
  - Both continue with Exharme promising an army "together with Lord Kamsell" and a speech: "The Goddess, the Saltmere, iron… the old cling to old things… Norzelia needs a new order… young standard-bearers, people like you and me."
- **Aesfrost-side scene** (`ms15_x31_b0_0010`):
  - Svarog and Sycras argue after Whiteholm falls, with Avlora *and* Thalas dead.
  - Svarog refuses relief troops unless Gustadolph comes to ask him in person.
- **Old prologue** (`ms01_x01_old`): 9 dialogue tables plus 8 maps, including its own battle. A different opening:
  - Narration: a joint mine-development venture among the three nations of the Saltiron War.
  - Prince **Frani** hosts guests at the "Sandbar Castle" for a ceremony and martial tournament. Clarus's trading company runs the betting.
  - Clarus introduces Avlora and "**Duke Exharme of Marcial**, newest of the Seven Saints".
  - Serenoa meets Frederica at the harbor ("the woman who will be my wife"). Bandits Trish and Travis attack, recognizing her rose-colored hair as Roselle.
  - Serenoa gets **three dialogue choices**.
  - Roland drops in incognito. **Symon is alive and well**, welcoming Frederica as a daughter.
  - Anna escorts **Dragan** and **Lyla** as the venture's representatives.
- **Early Chapter 6–7 drafts using the setting's early names** (`ms06_x07_*`, `ms07_hdr_*`, `ms07_x08_*`, `ms07_x09_*`):

  | Early name | Final name |
  |---|---|
  | Archduchy of **Blizmine** | Aesfrost |
  | Kingdom of **Riverwind** | Glenbrook |
  | House **Militaris** | Wolffort |
  | **Wallfort** Castle | Falcon's Nest / Wolffort |
  | Holy State of **Solstia** | Hyzante |
  | **Goldwind**, House **Falkus** | Landroi's lands and house |

  Content:
  - **Maxwell's last stand on the bridge.** He holds off Avlora so Roland can escape and falls. Avlora: "I admit it. You are strong. Second only to me."
  - **The prototype Chapter 7 vote, with a persuasion system:**
    - Serenoa picks dialogue replies; Erador gives a different answer to each.
    - Every companion has lines for receiving a **gift**.
    - Every companion has lines for siding with you, against you, and feeling betrayed.
    - A stated rule: "In a tie, the acting head of the house makes the final decision."
    - Roland's line is "my life is worthless now."
  - **Town-traps prep as an exploration level:**
    - Hidden bird-statue pedestals: one under a market stall that Hughette helps find.
    - A shop, a "go to barracks" prompt, and townsfolk lines.
    - Persuasion choices with Roland and Erador.
  - **Early "hand Roland over" branch:**
    - Gustadolph takes Roland and reveals **Cordelia alive** as his puppet.
    - Wolffort is ordered, in Roland's name, to attack **Landroi's Goldwind**.
    - A full exploration level: terraced wheat fields, wind-powered lifts, villager lines, and a fire-arrow trap planned against you.
    - Landroi dies: "Regret…! And yet, this is what I wished for…!"
    - Then Roland's **public execution** is scheduled, and Wolffort is ordered to attend.
- **Alternate recruitment and character-story scenes:**
  - Narve's arrival (English);
  - Ezana's arrival, a shaman who doubted the Salt Goddess faith;
  - Medina's story: Lyla orders her to treat a Hyzantine believer before a sicker Roselle patient, who dies; Medina leaves the Academy and joins Serenoa.

## 2. Characters
- **Umbra (N209)**, イルジオン ("Illusion") in Japanese:
  - It has an English name and an exe character id.
  - The voice-test script loads it next to Lyla and Tenebris (N208).
  - It has no unit, portrait, sprite or stats, so it's cut or merged [read]. **[ask]** Is there an "Umbra" anywhere in the game?
  - Full search 2026-11-23 [read]: not even a `GOP_Unit_Master` row (the scripts' `chara.call` points at nothing); nothing named N209 in the pak. Both test scripts load `N209` **and** Sorsley's Guard Captain (`UNIT_MASTER_CH_M101_01`) side by side, and the captain's battle data is filed as `N303` (Dagger Fighter, Ch.10 route B), not `N209`. So Umbra is unlikely to be an early captain, though a later merge can't be ruled out [inferred].
- **Unused guest versions of four recruits** [read], all `bIsGuest`, using their player classes and weapons:
  - `P039` Rudolph (Hunter)
  - `P040` Frederica (Pyromancer)
  - `P046` Corentin (Cryomancer)
  - `P047` Milo (Dancer)
  - These were planned guest appearances.
  - They'd be cheap to recruit or reuse, since the classes `G004/G009/G010/G012` exist.
- **`Character/001`:** a second Serenoa sprite set (`T_CH_P001E`, its own frames: walk/run/atk/battle idle). Likely a prototype Serenoa [inferred]. Not yet viewed.
- Enemy stat rows never used:
  - Sycras's base `N106`;
  - Rebel Battlemage `M063_BOK_0`;
  - several "ANOTHER" variants of Bowman, Pikeman and Arcanist;
  - Svarog's guest rank-2 class **"Iron Master"** (`G104_2`).
- 175 unit records are never placed. They're mostly filler townsfolk and soldiers, plus some named roles:
  - "Landroi's / Sycras's / Patriatte's Subordinate";
  - "Ministry Official", "Supervisor", "Concierge", "Herald", "Orlaea".

## 3. Abilities [read; corrected 2026-11-17]

> **Correction.** Sweep 1 listed 108 "unused" abilities. Many are **unused duplicate rows of abilities that are in the game**: the shipped game uses another row with the same name. Examples:
> - Obsidian Anklet uses its accessory row.
> - Safe Haven, Pursuit Stance, Shielding Stance, Warming Up, Delayed Casting, Absorb Lightning, TP Region, Sprint, Fortify and Resist All all have live twins.
>
> These duplicates are not cut content. They're only useful as clean copies to edit.

### 3a. No live version anywhere [read]
Defined, with English text, but referenced by nothing else in the pak:
- no class, weapon tree, accessory or item uses them;
- no map, script or exe string references them;
- a raw byte scan of every asset confirms it.

| Ability | What it does |
|---|---|
| **TP Drain** | Magic damage to one enemy and absorb all their TP. |
| **Leg Trap** | Hidden trap that immobilizes whoever steps on it. Sibling of Steel Trap. |
| **Preserve TP** | Passive: +1 TP when you neither move nor act. |
| **Poised to Strike** | Passive: follow-up attacks deal more damage. |
| **Resist Paralysis/Immobility** | Passive immunity. The game uses other resist pairs. |
| **Fire Form / Ice Form** | Names only, no help text. |
| **Cobalt Blue Anklet** | Accessory name text only. No accessory row exists. |

**[ask]** You remember some of these from the game. If you can recall who had Preserve TP, Poised to Strike, Leg Trap or TP Drain, I'll trace that unit. It would point to a gap in the sweep.

Also unused:
- Unnamed buffs: `STR_UP`, `HP_UP`, `HP50PER_LOW_ALL_PARAM_UP` ("all stats up below 50% HP"), `ENEMY_UNIT_AROUND_STR/INT_UP`, `SWAP_FRIEND`, `HOT_PURSUIT`, `SELF_HEAL`, `MAGIC_CHARGE`, `E_DOUBLE_TURN`.
- Upgrade-tree tiers with no live twin:
  - Movement Up II/III, Jump Up II/III, Evasion Up III;
  - Strength/Magic/HP/Magic Defense Up III;
  - most elemental resistance tiers;
  - Physical/Magic Damage Down.
- "X Damage Up / TP −1" nodes:
  - Damage Up: Hawk Dive, Rush, Self-sacrifice, Splash;
  - TP −1: Scorch, Heal, Cure Wounds, Take Cover, Warped Space, Decoy, Straight Shot, Shield Bash.

Statuses:
- **Stun** has no live version.
- Ice and Wind Absorption only have debug versions in use.
- Lightning Absorption is live (via Absorb Lightning).

## 4. Items, equipment, music
- **Armor slots (head/body)**: test rows only. An armor system was planned [read].
- Generic class weapons `C_SWORD/SPEAR/SHIELD/BOW/STAFF_LV1/LV2` and a "Hidden Knife" exist, unused [read].
- Music no script calls [read]:
  - `BGM_M13_JIN_JOIN` (join jingle?)
  - `BGM_M62_JIN_JUDGE`
  - `BGM_M63_SYS_VOTE`
  - **[ask]** whether you recognize them in game.
- Prototype music `BGM_PP_*` is used only by old prototype scripts.

## 5. Prototype ("PrePro" = pre-production) leftovers [read]
- Old battle scripts return to `Title_PrePro` and use `BGM_PP_140`:
  - `ms10_x17`, `ms10_x19`: the pre-route-split chapter 10, with Silvio;
  - `ms19_x45_battle_02_old`: an older Idore fight;
  - `ms21_x48`: an older final chapter with Lyla, Idore and the Hierophant.
- **Preview maps (`Map/Preview/*`, ~120):** prototype versions of most areas, plus places absent from the final game:
  - a **Coliseum/Arena** (`P_C0_EX_Arena`, `P_B0_EX_Arena`, Japanese place name 闘技場 under "C0");
  - a **burned Falkes street**;
  - a hideout;
  - an "X" region (Centralia salt lake, fields, river);
  - Hyzante rooms.
- Prototype `BATTLE_UNITPARAM_OCT_CH_*` ids appear in Lua; the rows no longer exist.
- `Chapter0/` scripts, `Level/PrePro_00-02`, and `B_*` research levels.
- **Character History** feature: 28 entries, all **placeholder** text ("Corentin's 序/破/急 content, temporary text").
  - Nine character-story slots get three acts each: Corentin, Hossabara, Medina, Jens, Flanagan, Groma, Piccoletta, Decimal, plus CS25.
  - CS25 is Lionel's slot, but its placeholder says "Flanagan" (copy-paste).
  - A per-recruit history screen was planned and never written.

## 6. Debug and dev tools in the shipping pak [read]

Short version:
- The whole menu UI and most of the C++ behind it ship.
  - It includes everyone joins the party, open all shops, ignore class-up and weapon conditions, unlock all mock battles and side stories, conviction editing, force vote results, always crit, unlimited TP, instant win, weather control, and more.
  - It boots via a `GameDefaultMap` override to `DebugTitle` [community].
  - The in-battle opener (View/Select button) relies on a settings property that was stripped, so it likely doesn't work [inferred].
- Maps `System/DebugTitle`, `Debug/Level/DebugMenuLevel`, `TestMap/DebugScriptStart`.
- Blueprints `BP_DebugTitle`, `BP_DebugMenuOpenActor`, `DebugMenuSystem`.
- `DefaultEngine.ini`: `EditorStartupMap=DebugTitle`, `GameDefaultMap=StartUp`.
- **Modding lead [inferred, untested]:** a pak override of the default map might boot into the debug title or menu. Shipping builds often strip debug code, so this may be a dead end.
- About 30 test maps (`TestMap/Battle/*`: AI, gimmicks, trolley, route search) and the debug Lua (`Develop/`, `TestGameFlow/`, `Debug_Scenario/`).
  - They're useful references for scripting custom battles.

## 7. Modding value (my ranking)
1. **Tourney final vs Maxwell** (1a): script, map and dialogue all exist. Wire it as a mock battle via `GOP_Quest_Info`.
   - Missing: English intro text (translatable), and possibly a proper unit record for the Dawnspear.
2. **Chapter 17 duels** (1b) and **Jerrom / Avlora battles** (1c, 1d): playable scripts and maps, so they're mock-battle candidates right now.
   - They also give enemy Roland, Frederica and Benedict stats (N402–N404) for future kits.
3. **Unused abilities** (3a): drop-in fill-ins that are genuinely "from the game's data" (TP Drain, Leg Trap, Preserve TP, Poised to Strike).
4. **Guest versions of Rudolph / Frederica / Corentin / Milo** (2).
5. Prototype Coliseum and other preview maps (5): candidates for custom-map work later.

## Full-detail appendix
The complete dumps behind this summary (every cut line with its Japanese original, every unused row, the cut battles' scripts) are
kept out of this repository because they are the game's own text and code.

## Not yet swept
- Voice lines (4,648 unreferenced; mostly variants).
- Sound effects, effect assets.
- Japanese-only lines in other scenario tables (many "English" tables hold untranslated Japanese).
- Viewing the `Character/001` and preview-map art.
- The debug menu's actual contents.
